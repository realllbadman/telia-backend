import os
import asyncio
from typing import Any, Dict, List, Optional

import httpx


def _flatten_search_criteria(prefix: str, obj: Any, out: Dict[str, Any]) -> None:
	if isinstance(obj, dict):
		for k, v in obj.items():
			new_prefix = f"{prefix}[{k}]"
			_flatten_search_criteria(new_prefix, v, out)
	elif isinstance(obj, list):
		for i, v in enumerate(obj):
			new_prefix = f"{prefix}[{i}]"
			_flatten_search_criteria(new_prefix, v, out)
	else:
		out[prefix] = obj


async def fetch_magento_products(
	search_criteria: Optional[Dict[str, Any]] = None,
	page_size: int = 5,
	max_pages: int = 10,
	timeout: float = 30.0,
) -> List[Dict[str, Any]]:
	base_url = os.getenv("MAGENTO_BASE_URL")
	token = os.getenv("MAGENTO_ACCESS_TOKEN")
	
	if not token:
		raise RuntimeError("MAGENTO_ACCESS_TOKEN environment variable is not set")

	endpoint = base_url.rstrip("/") + "/rest/fr/V1/products"

	headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

	items: List[Dict[str, Any]] = []

	page = 1
	retries = 3

	async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
		while page <= max_pages:
			params: Dict[str, Any] = {}
			params["searchCriteria[currentPage]"] = page
			params["searchCriteria[pageSize]"] = page_size

			if search_criteria:
				flat: Dict[str, Any] = {}
				_flatten_search_criteria("searchCriteria", search_criteria, flat)
				params.update(flat)

			attempt = 0
			while True:
				try:
					resp = await client.get(endpoint, params=params)
				except (httpx.RequestError, asyncio.TimeoutError) as exc:
					attempt += 1
					if attempt <= retries:
						await asyncio.sleep(0.5 * attempt)
						continue
					raise RuntimeError(f"Request failed: {exc}") from exc

				if resp.status_code == 200:
					data = resp.json()
					page_items = data.get("items", [])
					if not isinstance(page_items, list):
						raise RuntimeError("Unexpected response structure: 'items' is not a list")
					items.extend(page_items)

					if len(page_items) < page_size:
						return items
					page += 1
					break

				if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
					attempt += 1
					await asyncio.sleep(0.5 * attempt)
					continue

				try:
					err = resp.json()
				except Exception:
					err = resp.text
				raise RuntimeError(f"Magento API error {resp.status_code}: {err}")

	return items


class ChatService:
	@staticmethod
	async def recommend_products(message: str, user_id: int):
		try:
			items = await fetch_magento_products(page_size=5, max_pages=10)
		except Exception:
			items = []

		recommendations = []
		for it in items:
			prod_id = str(it.get("id") or it.get("sku") or "")
			name = it.get("name") or it.get("custom_attributes", {}).get("name") or ""
			sku = it.get("sku") or ""
			price = 0.0
			if isinstance(it.get("price"), (int, float)):
				price = float(it.get("price"))
			else:
				ca = it.get("custom_attributes")
				if isinstance(ca, list):
					for attr in ca:
						if attr.get("attribute_code") == "price":
							try:
								price = float(attr.get("value", 0))
							except Exception:
								price = 0.0
							break

			recommendations.append({
				"id": prod_id,
				"name": name,
				"sku": sku,
				"price": price,
				"relevance_score": None,
			})

		return {"message": f"Recommendations for user {user_id}", "recommendations": recommendations}

