"""One-off diagnostic: PATCH kzvСсылкаНаКопию for a given invoice GUID."""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid

import httpx

from app.config import get_settings

ENTITY = "Document_СчетФактураВыданный"
SELECT = "Ref_Key,Number,Date,Posted,DeletionMark,kzvСсылкаНаКопию,ПредставлениеНомера"


async def probe(guid: uuid.UUID, storage_link: str | None) -> None:
    s = get_settings()
    url = f"/{ENTITY}(guid'{guid}')"
    async with httpx.AsyncClient(
        base_url=s.odata_base_url.rstrip("/"),
        auth=(s.odata_admin_user, s.odata_password),
        timeout=s.odata_timeout_seconds,
        headers={"Accept": "application/json"},
    ) as client:
        get_resp = await client.get(url, params={"$format": "json", "$select": SELECT})
        print("GET", get_resp.status_code)
        if get_resp.status_code != 200:
            print(get_resp.text[:2000])
            return
        doc = get_resp.json()
        print(json.dumps(doc, ensure_ascii=False, indent=2))

        link = storage_link or doc.get("kzvСсылкаНаКопию") or r"\\probe\test.pdf"
        patch_resp = await client.patch(
            url, json={"kzvСсылкаНаКопию": link}, params={"$format": "json"}
        )
        print("PATCH", patch_resp.status_code)
        if patch_resp.status_code in (200, 204):
            verify = await client.get(url, params={"$format": "json", "$select": "kzvСсылкаНаКопию"})
            print("verified:", verify.json().get("kzvСсылкаНаКопию", "")[:200])
        else:
            print(patch_resp.text[:2500])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--guid", default="0b41a1ed-0b05-11f1-92b3-00155d060d01")
    p.add_argument("--link", default=None)
    args = p.parse_args()
    asyncio.run(probe(uuid.UUID(args.guid), args.link))


if __name__ == "__main__":
    main()
