import asyncio
import logging


log = logging.getLogger(__name__)


class ConfigTableRecord(object):
    _data = dict()

    def __init__(self, config, record):
        self._config = config
        self._data = dict()
        self._dirty = set()

        for key, value in record.items():
            self._data[key] = value

    def __getattr__(self, key):
        if key in self._data:
            return self._data[key]

    def __setattr__(self, key, value):
        if key in self._data:
            self.set(key, value)
        else:
            self.__dict__[key] = value

    def _build_dirty(self, start_at=1):
        return ", ".join(
            "{} = ${}".format(key, idx + start_at)
            for idx, key in enumerate(self._dirty)
        )

    def _set_dirty(self, key):
        if key not in self._data:
            raise AttributeError(
                "Attempted to set key {} to dirty, but it does not exist".format(key)
            )
        self._dirty.add(key)

    def _clear_dirty(self):
        self._dirty.clear()

    def get(self, key):
        if key in self._data:
            return self._data[key]
        else:
            raise AttributeError("Key '{}' not defined in this table.".format(key))

    def set(self, key, value):
        if key not in self._data:
            raise AttributeError("Key '{}' not defined in this table.".format(key))

        self._data[key] = value
        self._set_dirty(key)

    async def update(self, **kwargs):
        for key, val in kwargs.items():
            self.set(key, val)

        if not self._dirty:
            raise ValueError("No values dirty for table {}".format(self._config.table))

        query = "UPDATE {} SET {} WHERE {}".format(
            self._config.table,
            self._build_dirty(len(self._config.primary) + 1),
            self._config.build_predicate(),
        )

        keys = tuple(self._data[primary] for primary in self._config.primary)
        values = tuple(self._data[key] for key in self._dirty)

        await self._config.bot.db.execute(query, *keys, *values)

        self._clear_dirty()


class ConfigTable:
    def __init__(self, bot, table, primary, record_class=None):
        record_class = record_class or ConfigTableRecord

        if record_class is not ConfigTableRecord and not issubclass(
            record_class, ConfigTableRecord
        ):
            raise TypeError("entry_class must inherit from ConfigTableEntry.")

        if isinstance(primary, str):
            primary = (primary,)
        elif not isinstance(primary, tuple):
            raise TypeError("Primary keys must be tuple or string.")

        self.bot = bot
        self.table = table
        self.primary = primary
        self.entries = dict()

        self._record_class = record_class
        self._lock = asyncio.Lock()
        self._non_existent = set()

        log.debug("Constructed ConfigTable for table %s with keys %s", table, primary)

    def build_predicate(self, start_at=1):
        return " AND ".join(
            "{} = ${}".format(key, idx + start_at)
            for idx, key in enumerate(self.primary)
        )

    def get_keys_from_record(self, record):
        return tuple(record.get(primary) for primary in self.primary)

    @property
    def _insert_query(self):
        return "INSERT INTO {} ({}) VALUES ({})".format(
            self.table,
            ", ".join(self.primary),
            ", ".join("${}".format(idx + 1) for idx, _ in enumerate(self.primary)),
        )

    async def insert_record(self, record, keys=None):
        keys = keys or self.get_keys_from_record(record)

        if keys in self._non_existent:
            self._non_existent.remove(keys)

        log.debug("Inserting record with keys %s for table %s", keys, self.table)

        entry = self._record_class(self, record)
        self.entries[keys] = entry

        return entry

    async def get_entry(self, *keys, construct=True):
        keys = tuple(keys)

        for key in keys:
            if not isinstance(key, int):
                raise TypeError("Primary key must be int.")

        if not construct and keys in self._non_existent:
            return None

        async with self._lock:
            if keys in self.entries:
                return self.entries[keys]

            get_query = (
                "SELECT * FROM {} WHERE ".format(self.table) + self.build_predicate()
            )

            record = await self.bot.db.fetchrow(get_query, *keys)

            if record is None:
                if not construct:
                    self._non_existent.add(keys)
                    return None
                elif keys in self._non_existent:
                    self._non_existent.remove(keys)

                await self.bot.db.execute(self._insert_query, *keys)
                record = await self.bot.db.fetchrow(get_query, *keys)

            return await self.insert_record(record, keys=keys)

    def has_entry(self, *keys):
        return tuple(keys) in self.entries

    async def clear_entry(self, *keys):
        """Returns True if key(s) found in entries dict."""

        keys = tuple(keys)

        async with self._lock:
            if keys in self._non_existent:
                log.info(
                    "Clearing non-existent entry %s for table %s", keys, self.table
                )
                self._non_existent.remove(keys)

            removed = bool(self.entries.pop(keys, False))

            if removed:
                log.info("Clearing entry %s for table %s", keys, self.table)

            return removed
