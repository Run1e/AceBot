import logging
from asyncio import create_task, Event
from datetime import timedelta

import discord
from asyncspotify import Client, ClientCredentialsFlow, FullAlbum, FullArtist, FullTrack
from discord.ext import commands

from utils.time import pretty_datetime
from cogs.mixins import AceMixin
from config import SPOTIFY_ID, SPOTIFY_SECRET

log = logging.getLogger(__name__)
#logging.getLogger('asyncspotify').setLevel(logging.DEBUG)

SPOTIFY_ICON_URL = 'https://dashboard.snapcraft.io/site_media/appmedia/2017/12/spotify-linux-256.png'


class TrackConverter(commands.Converter):
	async def convert(self, ctx, query=None):
		track = await ctx.cog.sp.search_track(query)

		if track is None:
			raise commands.CommandError('No track found.')

		return await ctx.cog.sp.get_track(track.id)


class ArtistConverter(commands.Converter):
	async def convert(self, ctx, query=None):
		artist = await ctx.cog.sp.search_artist(query)

		if artist is None:
			raise commands.CommandError('No artist found.')

		return artist


class AlbumConverter(commands.Converter):
	async def convert(self, ctx, query=None):
		album = await ctx.cog.sp.search_album(query)

		if album is None:
			raise commands.CommandError('No album found.')

		return await ctx.cog.sp.get_album(album.id)


def get_url(images):
	return images[0].url if images else None


class Spotify(AceMixin, commands.Cog):
	'''
	Spotify stuff!
	Powered by [asyncspotify](https://github.com/Run1e/asyncspotify)
	'''

	_list_fmt = '{0}. [{1}]({2})'

	def __init__(self, bot):
		super().__init__(bot)

		self.event = Event()

		self.sp = Client(
			ClientCredentialsFlow(
				client_id=SPOTIFY_ID,
				client_secret=SPOTIFY_SECRET
			)
		)

		create_task(self.authorize())

	async def authorize(self):
		await self.sp.authorize()
		self.event.set()

	def cog_unload(self):
		create_task(self.sp.close())

	async def cog_check(self, ctx):
		if not self.event.is_set():
			await self.event.wait()

		return await self.bot.is_owner(ctx.author)

	def cog_command_error(self, ctx, error):
		raise error

	def _new_embed(self, **kwargs):
		return discord.Embed(color=0x1DB954, **kwargs)

	def _craft_track_embed(self, artist: FullArtist, track: FullTrack):
		#desc = 'on album *[{0}]({1})*'.format(track.album.name, track.album.link)

		e = self._new_embed(title='*' + track.name + '*', description=None, url=track.link)

		e.set_author(
			name=', '.join(artist.name for artist in track.artists),
			url=artist.link,
			icon_url=get_url(artist.images)
		)

		e.set_image(url=get_url(track.album.images))
		e.set_footer(text=track.uri, icon_url=SPOTIFY_ICON_URL)

		return e

	def _craft_artist_embed(self, artist: FullArtist, top_tracks=None, related_artists=None, albums=None):
		e = self._new_embed()

		artist_image = get_url(artist.images)

		e.set_image(url=artist_image)
		e.set_footer(text=artist.uri, icon_url=SPOTIFY_ICON_URL)

		e.set_author(
			name=artist.name,
			url=artist.link,
			icon_url=artist_image
		)

		if top_tracks:
			e.add_field(
				name='Top tracks',
				value='\n'.join(
					self._list_fmt.format(idx + 1, track.name, track.link) for idx, track in enumerate(top_tracks[:3])
				)
			)

		if albums:
			e.add_field(
				name='Albums',
				value='\n'.join(
					self._list_fmt.format(idx + 1, album.name, album.link) for idx, album in enumerate(albums[:3])
				)
			)

		if related_artists:
			e.add_field(
				name='Related artists',
				value='\n'.join(
					self._list_fmt.format(idx + 1, artist.name, artist.link)
					for idx, artist in
					enumerate(related_artists[:3])
				)
			)

		e.add_field(
			name='Popularity',
			value='{0}%'.format(artist.popularity)
		)

		e.add_field(
			name='Followers',
			value=artist.follower_count
		)

		return e

	def _craft_album_embed(self, artist: FullArtist, album: FullAlbum):
		e = self._new_embed(title=album.name, url=album.link)

		e.set_author(name=artist.name, url=artist.link, icon_url=get_url(artist.images))
		e.set_footer(text=album.uri, icon_url=SPOTIFY_ICON_URL)
		e.set_image(url=get_url(album.images))

		e.add_field(name='Songs', value=str(len(album.tracks)))

		runtime = timedelta()
		for track in album.tracks:
			runtime += track.duration

		e.add_field(name='Runtime', value='{0} minutes'.format(round(runtime.total_seconds() / 60)))

		e.add_field(name='Popularity', value='{0}%'.format(album.popularity))
		e.add_field(name='Released', value=pretty_datetime(album.release_date, ignore_time=True))

		if album.genres:
			e.add_field(
				name='Genres',
				value=', '.join(album.genres)
			)

		return e

	async def _get_playing(self, member):
		for act in member.activities:
			if isinstance(act, discord.Spotify):
				return await self.sp.get_track(act._sync_id)

	@commands.command()
	@commands.cooldown(3, 10.0, commands.BucketType.user)
	async def playing(self, ctx):
		'''Show us what you're listening to!'''

		track = await self._get_playing(ctx.author)

		if track is None:
			raise commands.CommandError('You don\'t seem to be playing anything.')

		artist = await self.sp.get_artist(track.artists[0].id)
		if artist is None:
			return

		e = self._craft_track_embed(artist, track)
		await ctx.send(embed=e)

	@commands.command()
	@commands.cooldown(3, 10.0, commands.BucketType.user)
	async def track(self, ctx, *, query: TrackConverter):
		'''Search for a track.'''

		track: FullTrack = query

		if track is None:
			track = await self._get_playing(ctx.author)

		if track is None:
			raise commands.CommandError('You don\'t seem to be playing anything.')

		artist = await self.sp.get_artist(track.artists[0].id)
		if artist is None:
			return

		e = self._craft_track_embed(artist, track)
		await ctx.send(embed=e)

	@commands.command()
	@commands.cooldown(3, 10.0, commands.BucketType.user)
	async def artist(self, ctx, *, query: ArtistConverter):
		'''Search for an artist.'''

		artist: FullArtist = query

		top_tracks = await artist.top_tracks(market='NO')
		related_arists = await artist.related_artists()
		albums = await artist.albums(limit=3)

		e = self._craft_artist_embed(artist, top_tracks, related_arists, albums)
		await ctx.send(embed=e)

	@commands.command()
	@commands.cooldown(3, 10.0, commands.BucketType.user)
	async def album(self, ctx, *, query: AlbumConverter):
		'''Search for an album.'''

		album: FullAlbum = query

		artist = await self.sp.get_artist(album.artists[0].id)
		if artist is None:
			return

		e = self._craft_album_embed(artist, album)
		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Spotify(bot))
