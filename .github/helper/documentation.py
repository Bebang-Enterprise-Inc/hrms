import os
import sys
from urllib.parse import urlparse

import requests


def uri_validator(x):
	result = urlparse(x)
	return all([result.scheme, result.netloc, result.path])


def docs_link_exists(body, repository):
	allowed_repos = {"frappe/hrms", repository.lower()}
	for line in body.splitlines():
		for word in line.split():
			if word.startswith("http") and uri_validator(word):
				parsed_url = urlparse(word)
				if parsed_url.netloc == "github.com":
					parts = parsed_url.path.split("/")
					repo_path = "/".join(parts[1:3]).lower()
					if len(parts) == 5 and repo_path in allowed_repos:
						return True
				elif parsed_url.netloc == "docs.frappe.io":
					return True


if __name__ == "__main__":
	pr = sys.argv[1]
	repository = os.environ.get("GITHUB_REPOSITORY", "frappe/hrms")
	response = requests.get("https://api.github.com/repos/{}/pulls/{}".format(repository, pr))

	if response.ok:
		payload = response.json()
		title = (payload.get("title") or "").lower().strip()
		head_sha = (payload.get("head") or {}).get("sha")
		body = (payload.get("body") or "").lower()

		if title.startswith("feat") and head_sha and "no-docs" not in body and "backport" not in body:
			if docs_link_exists(body, repository):
				print("Documentation Link Found.")

			else:
				print("Documentation Link Not Found.")
				sys.exit(1)

		else:
			print("Skipping documentation checks...")
