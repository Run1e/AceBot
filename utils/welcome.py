def welcomify(user, guild, string):
	repl = {
		'guild': guild.name,
		'user': user.mention
	}

	for key, val in repl.items():
		string = string.replace('{' + key + '}', val)

	return string
