import os
import time
import requests


API_URL = "https://api.rule34.xxx/index.php"

TAG_TYPES = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}


def is_blocked(tags, blocked):
    if not blocked:
        return False

    blocked_set = {
        str(x).strip().lower()
        for x in blocked
        if str(x).strip()
    }

    for tag in tags:
        if str(tag).strip().lower() in blocked_set:
            return True

    return False


class Rule34Parser:

    def __init__(self, settings):
        self.settings = settings

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        })

        self.api_user_id = str(
            settings.get(
                "api_user_id",
                ""
            )
        ).strip()

        self.api_key = str(
            settings.get(
                "api_key",
                ""
            )
        ).strip()

        self.tag_cache = {}

    def _request(
        self,
        params,
        timeout=30
    ):
        last_error = None

        for attempt in range(3):
            try:
                response = self.session.get(
                    API_URL,
                    params=params,
                    timeout=timeout
                )

                response.raise_for_status()

                return response

            except requests.RequestException as e:
                last_error = e

                if attempt < 2:
                    time.sleep(2)

        raise last_error

    def _base_params(self):
        params = {}

        if self.api_user_id:
            params["user_id"] = self.api_user_id

        if self.api_key:
            params["api_key"] = self.api_key

        return params

    def list_post_ids(
        self,
        tags,
        page=0
    ):
        params = self._base_params()

        params.update({
            "page": "dapi",
            "s": "post",
            "q": "index",
            "limit": 100,
            "pid": page,
            "tags": " ".join(
                str(tag).strip()
                for tag in tags
                if str(tag).strip()
            )
        })

        response = self._request(
            params
        )

        try:
            root = response.text

            from xml.etree import ElementTree

            tree = ElementTree.fromstring(
                root
            )

        except Exception:
            return []

        result = []

        for item in tree.findall(".//post"):
            post_id = item.attrib.get(
                "id"
            )

            if not post_id:
                continue

            try:
                result.append(
                    int(post_id)
                )
            except ValueError:
                continue

        return result

    def get_post(self, post_id):
        params = self._base_params()

        params.update({
            "page": "dapi",
            "s": "post",
            "q": "index",
            "id": post_id
        })

        response = self._request(
            params
        )

        try:
            from xml.etree import ElementTree

            tree = ElementTree.fromstring(
                response.text
            )

        except Exception:
            return None

        item = tree.find(".//post")

        if item is None:
            return None

        data = item.attrib

        raw_tags = data.get(
            "tags",
            ""
        )

        all_tags = [
            tag.strip()
            for tag in raw_tags.split()
            if tag.strip()
        ]

        categories = self._categorize_tags(
            all_tags
        )

        file_url = data.get(
            "file_url"
        )

        if not file_url:
            return None

        return {
            "id": int(
                data.get(
                    "id",
                    post_id
                )
            ),
            "file_url": file_url,
            "all_tags": all_tags,

            "characters": categories[
                "character"
            ],

            "fandoms": categories[
                "copyright"
            ],

            "general": categories[
                "general"
            ],

            "artist": categories[
                "artist"
            ],

            "meta": categories[
                "meta"
            ],
        }

    def _get_tag_type(self, tag):
        tag = str(tag).strip().lower()

        if not tag:
            return None

        if tag in self.tag_cache:
            return self.tag_cache[tag]

        params = self._base_params()

        params.update({
            "page": "dapi",
            "s": "tag",
            "q": "index",
            "name": tag,
            "limit": 1
        })

        try:
            response = self._request(
                params
            )

            from xml.etree import ElementTree

            tree = ElementTree.fromstring(
                response.text
            )

            item = tree.find(".//tag")

            if item is None:
                self.tag_cache[tag] = 0
                return 0

            tag_type = int(
                item.attrib.get(
                    "type",
                    0
                )
            )

            self.tag_cache[tag] = tag_type

            return tag_type

        except Exception:
            return 0

    def _categorize_tags(self, tags):
        result = {
            "general": [],
            "artist": [],
            "copyright": [],
            "character": [],
            "meta": [],
        }

        for tag in tags:
            tag_type = self._get_tag_type(
                tag
            )

            category = TAG_TYPES.get(
                tag_type,
                "general"
            )

            result[category].append(
                tag
            )

        return result

    def download(
        self,
        url,
        target_path
    ):
        response = self.session.get(
            url,
            timeout=60,
            stream=True
        )

        response.raise_for_status()

        content_type = (
            response.headers.get(
                "Content-Type",
                ""
            ).lower()
        )

        extension = ""

        if "gif" in content_type:
            extension = ".gif"

        elif "mp4" in content_type:
            extension = ".mp4"

        elif "webm" in content_type:
            extension = ".webm"

        elif "png" in content_type:
            extension = ".png"

        elif (
            "jpeg" in content_type
            or "jpg" in content_type
        ):
            extension = ".jpg"

        if not extension:
            clean_url = url.split(
                "?",
                1
            )[0]

            _, ext = os.path.splitext(
                clean_url
            )

            if ext:
                extension = ext.lower()

        if not extension:
            extension = ".bin"

        path = target_path + extension

        with open(
            path,
            "wb"
        ) as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

        return path