import frappe
import json
import requests
from datetime import date, datetime
from typing import Dict, Any, Optional
from frappe import _


class DigitaxAPIException(Exception):
	"""Custom exception for DigiTax API errors"""

	pass


class DigitaxClient:
	"""Client for interacting with the DigiTax API"""

	def __init__(self, company: Optional[str] = None) -> None:
		"""
		Initialize the DigiTax client

		Args:
			company: Company name. Defaults to user's default company if not provided
		"""
		self.company = company or self._get_default_company()
		self.settings = self._get_settings()
		self.base_url = self.settings.base_url
		self.api_key = self._get_api_key()
		self.headers = self._build_auth_headers()
		self.timeout = 20

	def _get_default_company(self) -> str:
		"""Get the default company for the current user"""
		company = frappe.defaults.get_user_default("company")
		if not company:
			frappe.throw(_("No default company found for user"))
		return company

	def _get_settings(self):
		"""Fetch NRS settings for the company"""
		if not frappe.db.exists("NRS Settings", {"company": self.company}):
			frappe.throw(
				_("NRS Settings not found for company {0}").format(self.company),
				title=_("Configuration Error"),
			)
		return frappe.get_doc("NRS Settings", {"company": self.company})

	def _get_api_key(self) -> str:
		"""Get the API key from the NRS Settings document"""
		api_key = self.settings.get_password(fieldname="api_key")

		if not api_key:
			frappe.throw(
				_("API Key not configured for settings {0}").format(self.settings.name),
				title=_("Configuration Error"),
			)

		return api_key

	def _build_auth_headers(self) -> Dict[str, str]:
		"""Build authentication headers for API requests"""
		return {"Content-Type": "application/json", "X-API-KEY": self.api_key}

	def _build_url(self, endpoint: str) -> str:
		"""Build the complete URL from base URL and endpoint"""
		base = self.base_url.rstrip("/")

		if not endpoint.startswith("/"):
			endpoint = f"/{endpoint}"

		return f"{base}{endpoint}"

	def _extract_error_message(self, error: requests.exceptions.HTTPError) -> str:
		try:
			response_data = error.response.json()
			return (
				response_data.get("message") or response_data.get("error") or str(error)
			)
		except:
			return error.response.text or str(error)

	def _validate_sales_tracking_permission(self):
		if not self.settings.allow_nrs_tracking_sales:
			raise DigitaxAPIException("Sales Tracking not allowed via settings")

	def _json_default(self, value):
		"""Serialize Python objects that the standard JSON encoder cannot handle."""
		if isinstance(value, (date, datetime)):
			return value.isoformat()

		raise TypeError(
			f"Object of type {type(value).__name__} is not JSON serializable"
		)

	def _dumps_json(self, data: Any) -> str:
		"""Dump JSON using app-safe serialization for dates and datetimes."""
		return json.dumps(data, indent=2, default=self._json_default)

	def post(
		self,
		endpoint: str,
		data: Dict[str, Any],
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Make a POST request to the DigiTax API

		Args:
			endpoint: API endpoint (e.g., "/items")
			data: Request payload
			reference_doctype: DocType of the document making this request (e.g., "Item")
			reference_docname: Name of the document making this request (e.g., "PRODUCT-001")

		Returns:
			Response data as dictionary or None if request fails

		Raises:
			DigitaxAPIException: If the API request fails
		"""
		self._validate_sales_tracking_permission()

		url = self._build_url(endpoint)
		integration_request = None

		try:
			# Create Integration Request to log this API call
			integration_request = self._create_integration_request(
				url=url,
				request_data=data,
				reference_doctype=reference_doctype,
				reference_docname=reference_docname,
			)

			frappe.logger().info(f"DigiTax API Request: POST {url}")
			frappe.logger().debug(f"Request data: {self._dumps_json(data)}")

			response = requests.post(
				url,
				headers=self.headers,
				data=self._dumps_json(data),
				timeout=self.timeout,
			)

			response.raise_for_status()
			response_data = response.json()

			frappe.logger().info(f"DigiTax API Response: {response.status_code}")
			frappe.logger().debug(f"Response data: {self._dumps_json(response_data)}")

			# Update Integration Request with successful response
			self._update_integration_request(
				integration_request=integration_request,
				status="Completed",
				response_data=response_data,
				status_code=response.status_code,
			)

			return response_data

		except requests.exceptions.HTTPError as e:
			self._handle_http_error(e, url, integration_request)
		except requests.exceptions.ConnectionError as e:
			self._handle_connection_error(e, url, integration_request)
		except requests.exceptions.Timeout as e:
			self._handle_timeout_error(e, url, integration_request)
		except requests.exceptions.RequestException as e:
			self._handle_generic_error(e, url, integration_request)
		except json.JSONDecodeError as e:
			self._handle_json_error(e, url, integration_request)

		return None

	def put(
		self,
		endpoint: str,
		path_param: str,
		data: Dict[str, Any],
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Make a PUT request to the DigiTax API

		Args:
			endpoint: API endpoint (e.g., "/items")
			path_param: Path parameter to append to endpoint (e.g., "item-id-123")
			data: Request payload
			reference_doctype: DocType of the document making this request (e.g., "Item")
			reference_docname: Name of the document making this request (e.g., "PRODUCT-001")

		Returns:
			Response data as dictionary or None if request fails

		Raises:
			DigitaxAPIException: If the API request fails
		"""
		self._validate_sales_tracking_permission()

		# Build endpoint with path parameter
		endpoint_with_param = f"{endpoint.rstrip('/')}/{path_param}"
		url = self._build_url(endpoint_with_param)
		integration_request = None

		try:
			# Create Integration Request to log this API call
			integration_request = self._create_integration_request(
				url=url,
				request_data=data,
				reference_doctype=reference_doctype,
				reference_docname=reference_docname,
				method="PUT",
			)

			frappe.logger().info(f"DigiTax API Request: PUT {url}")
			frappe.logger().debug(f"Request data: {self._dumps_json(data)}")

			response = requests.put(
				url,
				headers=self.headers,
				data=self._dumps_json(data),
				timeout=self.timeout,
			)

			response.raise_for_status()
			response_data = response.json()

			frappe.logger().info(f"DigiTax API Response: {response.status_code}")
			frappe.logger().debug(f"Response data: {self._dumps_json(response_data)}")

			# Update Integration Request with successful response
			self._update_integration_request(
				integration_request=integration_request,
				status="Completed",
				response_data=response_data,
				status_code=response.status_code,
			)

			return response_data

		except requests.exceptions.HTTPError as e:
			self._handle_http_error(e, url, integration_request)
		except requests.exceptions.ConnectionError as e:
			self._handle_connection_error(e, url, integration_request)
		except requests.exceptions.Timeout as e:
			self._handle_timeout_error(e, url, integration_request)
		except requests.exceptions.RequestException as e:
			self._handle_generic_error(e, url, integration_request)
		except json.JSONDecodeError as e:
			self._handle_json_error(e, url, integration_request)

		return None

	def get(
		self,
		endpoint: str,
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Make a GET request to the DigiTax API

		Args:
			endpoint: API endpoint (e.g., "/resources/invoice-types")
			reference_doctype: DocType of the document making this request
			reference_docname: Name of the document making this request

		Returns:
			Response data as dictionary or None if request fails

		Raises:
			DigitaxAPIException: If the API request fails
		"""
		url = self._build_url(endpoint)
		integration_request = None

		try:
			# Create Integration Request to log this API call
			integration_request = self._create_integration_request(
				url=url,
				request_data={},
				reference_doctype=reference_doctype,
				reference_docname=reference_docname,
				method="GET",
			)

			frappe.logger().info(f"DigiTax API Request: GET {url}")

			response = requests.get(url, headers=self.headers, timeout=self.timeout)

			response.raise_for_status()
			response_data = response.json()

			frappe.logger().info(f"DigiTax API Response: {response.status_code}")
			frappe.logger().debug(f"Response data: {self._dumps_json(response_data)}")

			# Update Integration Request with successful response
			self._update_integration_request(
				integration_request=integration_request,
				status="Completed",
				response_data=response_data,
				status_code=response.status_code,
			)

			return response_data

		except requests.exceptions.HTTPError as e:
			self._handle_http_error(e, url, integration_request)
		except requests.exceptions.ConnectionError as e:
			self._handle_connection_error(e, url, integration_request)
		except requests.exceptions.Timeout as e:
			self._handle_timeout_error(e, url, integration_request)
		except requests.exceptions.RequestException as e:
			self._handle_generic_error(e, url, integration_request)
		except json.JSONDecodeError as e:
			self._handle_json_error(e, url, integration_request)

		return None

	def _create_integration_request(
		self,
		url: str,
		request_data: dict,
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
		method: str = "POST",
	):
		"""Create an Integration Request document to log the API call"""
		try:
			integration_request = frappe.get_doc(
				{
					"doctype": "Integration Request",
					"integration_type": "Remote",
					"integration_request_service": reference_doctype,
					"method": method,
					"url": url,
					"request_headers": json.dumps(
						self._sanitize_headers(self.headers), indent=2
					),
					"data": self._dumps_json(request_data),
					"reference_doctype": reference_doctype,
					"reference_docname": reference_docname,
					"status": "Queued",
				}
			)
			integration_request.insert(ignore_permissions=True)
			frappe.db.commit()
			return integration_request
		except Exception as e:
			frappe.logger().error(f"Failed to create Integration Request: {str(e)}")
			return None

	def _update_integration_request(
		self,
		integration_request,
		status: str,
		response_data: Optional[dict] = None,
		error: Optional[str] = None,
		status_code: Optional[int] = None,
	):
		"""Update Integration Request with response or error"""
		if not integration_request:
			return

		try:
			integration_request.status = status

			if response_data:
				integration_request.output = self._dumps_json(response_data)

			if error:
				integration_request.error = str(error)

			if status_code:
				integration_request.status_code = status_code

			integration_request.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.logger().error(f"Failed to update Integration Request: {str(e)}")

	def _sanitize_headers(self, headers: dict) -> dict:
		"""Remove sensitive information from headers before logging"""
		sanitized = headers.copy()
		if "X-API-KEY" in sanitized:
			sanitized["X-API-KEY"] = "***REDACTED***"
		return sanitized

	def _handle_http_error(
		self, error: requests.exceptions.HTTPError, url: str, integration_request=None
	) -> None:
		"""Handle HTTP errors (4xx, 5xx)"""
		error_message = self._extract_error_message(error)

		frappe.log_error(
			title="DigiTax HTTP Error",
			message=f"URL: {url}\nStatus: {error.response.status_code}\nError: {error_message}",
		)

		# Update Integration Request with error
		self._update_integration_request(
			integration_request=integration_request,
			status="Failed",
			error=error_message,
			status_code=error.response.status_code,
			response_data=self._safe_json_response(error.response),
		)

		raise DigitaxAPIException(f"HTTP {error.response.status_code}: {error_message}")

	def _handle_connection_error(
		self,
		error: requests.exceptions.ConnectionError,
		url: str,
		integration_request=None,
	) -> None:
		"""Handle connection errors"""
		error_message = (
			"Failed to connect to DigiTax API. Please check your network connection."
		)

		frappe.log_error(
			title="DigiTax Connection Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _handle_timeout_error(
		self, error: requests.exceptions.Timeout, url: str, integration_request=None
	) -> None:
		"""Handle timeout errors"""
		error_message = "DigiTax API request timed out. Please try again."

		frappe.log_error(
			title="DigiTax Timeout Error",
			message=f"URL: {url}\nTimeout: {self.timeout}s\nError: {str(error)}",
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _handle_generic_error(
		self,
		error: requests.exceptions.RequestException,
		url: str,
		integration_request=None,
	) -> None:
		"""Handle generic request errors"""
		frappe.log_error(
			title="DigiTax Request Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(
			f"An error occurred while communicating with DigiTax API: {str(error)}"
		)

	def _handle_json_error(
		self, error: json.JSONDecodeError, url: str, integration_request=None
	) -> None:
		"""Handle JSON decode errors"""
		error_message = "Invalid response received from DigiTax API."

		frappe.log_error(
			title="DigiTax JSON Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _safe_json_response(self, response):
		"""Safely extract JSON from response"""
		try:
			return response.json()
		except:
			return {"raw_response": response.text[:1000]}  # Limit length
