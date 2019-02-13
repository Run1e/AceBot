

length = 100
messages = []

def push_message(message_id):
	messages.insert(0, message_id)
	if len(messages) > length:
		messages.pop()

def bot_deleted(message_id):
	return message_id in messages