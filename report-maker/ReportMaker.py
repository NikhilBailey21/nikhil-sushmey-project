import json
import os
import logging
from datetime import datetime
from enum import IntEnum
import vertexai
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)

class ReportMaker:
    def __init__(self):
        project_id = os.getenv("PROJECT_ID")
        location = "us-central1"
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-1.5-pro")

    def make_report(self, csv_id: int) -> str:
        csv_string = self._get_csv_string_from_database(csv_id) # Database Call
 
        for attemptCount in range(3):
            try:
                transaction_data = self._convert_transaction_data_to_structured_json(csv_string) # VertexAI Call
                if not self._validate_structured_json(transaction_data):
                    continue
                transaction_list = self._convert_structured_json_to_transaction_objects(transaction_data)

                metrics = self._calculate_metrics_from_transaction_list(transaction_list)
                markdown_report = self._make_markdown_report_from_transaction_list(transaction_list, metrics) # VertexAI Call
                self._upload_markdown_report_to_database(csv_id, markdown_report) # Database Call
                return markdown_report

            except Exception as error:
                if attemptCount == 2:
                    raise error
                else:
                    logger.info(f"Failed to make report, attempt {attemptCount + 1} of 3")

        raise Exception("Failed to convert transaction data to structured JSON after all attempts.")

    def _get_csv_string_from_database(self, csv_id: int) -> str:
        pass

    def _convert_transaction_data_to_structured_json(self, transaction_data: str):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amountInCents": {"type": "integer"},
                    "description": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": VALID_CATEGORIES
                    },
                    "date": {"type": "string"}
                },
                "required": ["amountInCents", "description", "category", "date"]
            }
        }

        vertexai_prompt = f"""Convert the following transaction data into structured JSON.
Each row should be a single transaction.
The description should be copied from the transaction description field.
The date should be extracted from the transaction data and formatted as YYYY-MM-DD (ISO 8601 format).
The category should be determined by which category the transaction most closely fits into. Use exactly one of these category values:
{json.dumps(VALID_CATEGORIES)}
The amount should be the same as the transaction amount in cents (multiply by 100 if needed), positive for purchases or debits, but negative for refunds or credits.
\n\nTransaction data:\n\n{transaction_data}
"""

        response = self.model.generate_content(vertexai_prompt,
            generation_config={
                "response_schema": schema,
                "response_mime_type": "application/json"
            }
        )

        return json.loads(response.text)

    def _validate_structured_json(self, structured_json: list) -> bool:
        """
        Validate that the structured JSON matches the expected schema.
        
        Args:
            structured_json: List of transaction dictionaries
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(structured_json, list):
            return False
        
        for transaction in structured_json:
            if not isinstance(transaction, dict):
                return False
            
            if "amountInCents" not in transaction:
                return False
            if "description" not in transaction:
                return False
            if "category" not in transaction:
                return False
            if "date" not in transaction:
                return False
            
            if not isinstance(transaction["amountInCents"], int):
                return False
            if not isinstance(transaction["description"], str):
                return False
            if not isinstance(transaction["category"], str):
                return False
            if not isinstance(transaction["date"], str):
                return False
            
            if transaction["category"] not in VALID_CATEGORIES:
                return False

            # Validate that the date is a valid date in the ISO 8601 format (YYYY-MM-DD)
            try:
                datetime.strptime(transaction["date"], "%Y-%m-%d")
            except (ValueError, TypeError):
                return False
        
        return True

    def _convert_structured_json_to_transaction_objects(self, structured_json: list) -> list['Transaction']:
        """
        Convert structured JSON (list of dicts) to a list of Transaction objects.
        
        Args:
            structured_json: List of transaction dictionaries with keys:
                - amountInCents (int)
                - description (str)
                - category (str)
                - date (str) - ISO 8601 format (YYYY-MM-DD), will be converted to datetime
                
        Returns:
            List of Transaction objects with date as datetime object
        """
        transactions = []
        for transaction_dict in structured_json:
            date_obj = datetime.strptime(transaction_dict["date"], "%Y-%m-%d")
            transaction = Transaction(
                amountInCents=transaction_dict["amountInCents"],
                description=transaction_dict["description"],
                category=transaction_dict["category"],
                date=date_obj
            )
            transactions.append(transaction)
        return transactions

    def _calculate_metrics_from_transaction_list(self, transaction_list: list['Transaction']) -> dict:
        pass

    def _make_markdown_report_from_transaction_list(self, transaction_list: list['Transaction'], metrics: dict) -> str:
        pass

    def _upload_markdown_report_to_database(self, csv_id: int, markdown_report: str):
        pass

class Category(IntEnum):
    """Transaction categories with their numerical IDs."""
    EVERYDAY_ESSENTIALS = 1
    SHOPPING_RETAIL = 2
    TRAVEL = 3
    ENTERTAINMENT_DINING = 4
    UTILITIES_HOME_SERVICES = 5
    HEALTH_WELLNESS = 6
    AUTOMOTIVE = 7
    FINANCIAL_INSURANCE = 8
    EDUCATION_PROFESSIONAL_SERVICES = 9
    CHARITABLE_MISCELLANEOUS = 10
    
    @property
    def display_name(self) -> str:
        """Get the display name for the category."""
        display_names = {
            Category.EVERYDAY_ESSENTIALS: "Everyday & Essentials",
            Category.SHOPPING_RETAIL: "Shopping & Retail",
            Category.TRAVEL: "Travel",
            Category.ENTERTAINMENT_DINING: "Entertainment & Dining",
            Category.UTILITIES_HOME_SERVICES: "Utilities & Home Services",
            Category.HEALTH_WELLNESS: "Health & Wellness",
            Category.AUTOMOTIVE: "Automotive",
            Category.FINANCIAL_INSURANCE: "Financial & Insurance",
            Category.EDUCATION_PROFESSIONAL_SERVICES: "Education & Professional Services",
            Category.CHARITABLE_MISCELLANEOUS: "Charitable & Miscellaneous"
        }
        return display_names[self]
    
    @classmethod
    def from_display_name(cls, display_name: str) -> 'Category':
        """Get Category enum from display name."""
        for category in cls:
            if category.display_name == display_name:
                return category
        raise ValueError(f"Unknown category display name: {display_name}")

VALID_CATEGORIES = [category.display_name for category in Category]

class Transaction:
    def __init__(self, amountInCents: int, description: str, category: str, date: datetime):
        self.amountInCents = amountInCents
        self.description = description
        self.category = category
        self.date = date

