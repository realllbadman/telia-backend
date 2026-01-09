import os
import asyncio
from typing import Any, Dict, List, Optional

import httpx


def _flatten_search_criteria(prefix: str, obj: Any, out: Dict[str, Any]) -> None:
	"""Recursively flatten a search_criteria structure into Magento bracketed params.

	Examples:
		{'filter_groups': [{'filters': [{'field': 'sku', 'value': 'ABC'}]}]}
	becomes:
		searchCriteria[filter_groups][0][filters][0][field]=sku
		searchCriteria[filter_groups][0][filters][0][value]=ABC
	"""
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
	page_size: int = 10,
	max_pages: int = 5,
	timeout: float = 30.0,
) -> List[Dict[str, Any]]:
	"""Fetch products from Magento 2 using the REST API `/V1/products`.

	- Reads `MAGENTO_BASE_URL` and `MAGENTO_TOKEN` from environment.
	- Uses `httpx.AsyncClient`.
	- Supports `search_criteria` (nested dict) which is flattened into
	  `searchCriteria[...]` query params expected by Magento.
	- Handles pagination and basic HTTP errors. Returns a list of product items.

	Args:
		search_criteria: Nested dict matching Magento searchCriteria structure.
		page_size: Number of items per page (Magento `searchCriteria[pageSize]`).
		max_pages: Safety cap on number of pages to fetch.
		timeout: Request timeout in seconds.

	Returns:
		List of product item dicts.
	"""
	base_url =  "https://staging-site.glotelho.cm/rest/fr/V1/"
	token =  "smftmxd38fpedqtbg3ydcbe1c6bqwjkq"
	if not base_url:
		raise RuntimeError("MAGENTO_BASE_URL environment variable is not set")
	if not token:
		raise RuntimeError("MAGENTO_TOKEN environment variable is not set")

	endpoint = base_url.rstrip("/") + "/rest/V1/products"

	headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

	items: List[Dict[str, Any]] = []

	page = 1
	retries = 3

	async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
		while page <= max_pages:
			params: Dict[str, Any] = {}
			# add page and pageSize
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

					# Stop when fewer items than page_size are returned
					if len(page_items) < page_size:
						return items

					# otherwise advance to next page
					page += 1
					break

				# handle rate limiting or server errors with retry
				if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
					attempt += 1
					await asyncio.sleep(0.5 * attempt)
					continue

				# other errors -> raise with details
				try:
					err = resp.json()
				except Exception:
					err = resp.text
				raise RuntimeError(f"Magento API error {resp.status_code}: {err}")

	return items

