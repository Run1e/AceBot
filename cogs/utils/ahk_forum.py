# ty capn! x2

import requests, re

from bs4 import BeautifulSoup, element


def getThread(url):
	s = requests.Session()
	print(url)

	tmpurl = re.sub("&start=\d+$", "", url)

	response = s.get(tmpurl)

	html = BeautifulSoup(response.text, "lxml")

	id = re.search("(?<=#)p\d*$", url)

	if (id != None):
		post = html.find("div", id=id.group(0))
	else:
		post = html.find("div", class_="post")

	user = post.find("dl", class_="postprofile")

	username = user.find("a", class_="username") if user.find("a", class_="username") else user.find("a", class_="username-coloured")

	icon = user.find("img", class_="avatar").get("src") if user.find("img", class_="avatar") else ""

	userUrl = username.get("href")
	username = username.text

	body = post.find("div", class_="postbody").find("div")
	title = body.find("a").text

	content = BeautifulSoup(str(body.find("div", class_="content")), "lxml")

	image = content.find("img", class_="postimage")

	if (image):
		image = image.get("src")

	for_all(content.find_all("div", class_="codebox"), lambda code: code.clear())

	for_all(content.find_all("blockquote"), lambda code, post=content: code.insert_after(post.new_tag("br")))

	toMarkdown(content)

	res = ""
	for child in content.descendants:
		if (is_Header(child)):
			break
		if (child.name == "br"):
			res += "\n"
		if (isinstance(child, element.NavigableString)):
			res += child

	lst = []
	i = 0
	for span in content.find_all("span"):
		if (is_Header(child)):
			lst.append({"head": span.text, "content": ""})
			bool = True
			for child in span.next_elements:
				if (is_Header(child)):
					break
				if (child.name == "br"):
					lst[i]["content"] += "\n"
				if (not bool and isinstance(child, element.NavigableString)):
					lst[i]["content"] += child
				bool = False
			lst[i]["content"] = re.sub("\n+", "\n", lst[i]["content"])
			i += 1

	return {"title": title, "user": {"name": username, "url": userUrl, "icon": icon}, "image": image,
			"description": re.sub("\n+", "\n", res), "content": lst}


def is_Header(tag):
	if (tag.name == "span" and tag.has_attr("style")):
		size = re.search("(?<=font-size: )\d+", tag.get("style"))
		if (size and int(size.group(0)) >= 150):
			return True
	return False


def for_all(lst, fun):
	for tag in lst:
		if (tag):
			fun(tag)


def toMarkdown(html):
	for_all(html.find_all("a", class_="postlink"),
			lambda link: link.replace_with("[" + link.text + "](" + link.get("href") + ")"))

	lst = {"strong": "**", "b": "**", "code": "`", "em": "*"}
	for key in lst:
		for_all(html.find_all(key), lambda code: code.replace_with(lst[key] + code.text + lst[key]))


def getIcon(url, html):
	for i in html.head.find_all("link"):
		if ("icon" in i.get("rel")):
			base = re.search("\.\w+\.\w+", url)
			if (base):
				return url[0:base.end(0)] + i.get("href")


def getTitle(html):
	return html.find("title").text


def getPreView(url):
	s = requests.Session()
	response = s.get(url)
	html = BeautifulSoup(response.text, "lxml")

	return {"title": getTitle(html), "icon": getIcon(url, html)}

