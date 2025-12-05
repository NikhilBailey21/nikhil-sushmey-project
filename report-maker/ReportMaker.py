from collections import defaultdict
import json
import os
import logging
from datetime import datetime
from enum import IntEnum
import statistics
import vertexai
from shared.db import get_db
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
        try:
            db = get_db()
            cursor = db.cursor()
            csv_string = cursor.execute(f"SELECT csv_content FROM uploaded_csvs WHERE csv_id='{csv_id}'")
            cursor.close()
        except Exception as e:
            logger.error(f"ReportMaker failed to connect to db: {e}")
            if cursor:
                cursor.close()
            raise
        return csv_string

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


    def _calculate_metrics_from_transaction_list(self, transaction_list: List['Transaction']) -> Dict:
        """
        Given a list of Transaction objects, calculate useful financial metrics
        and return both the metrics and the original transaction data as dicts.

        Output:
            metrics
        """
        
        # Defensive empty check
        if not transaction_list:
            return {
                    "summary": {
                        "totalSpend": 0,
                        "transactionCount": 0,
                        "avgTransaction": 0
                    }
            }

        # ----------------------
        # Helpers
        # ----------------------
        
        # total
        total_spend = sum(t.amountInCents for t in transaction_list)
        count = len(transaction_list)
        avg_txn = total_spend / count if count else 0

        # ----------------------
        # Category grouping
        # ----------------------
        category_groups = defaultdict(list)
        for tx in transaction_list:
            category_groups[tx.category].append(tx)
        
        category_totals = {
            cat: sum(t.amountInCents for t in txns)
            for cat, txns in category_groups.items()
        }

        category_counts = {
            cat: len(txns)
            for cat, txns in category_groups.items()
        }

        category_percentages = {
            cat: (category_totals[cat] / total_spend) if total_spend else 0
            for cat in category_totals.keys()
        }

        # ----------------------
        # Merchant/Description clustering
        # ----------------------
        desc_groups = defaultdict(list)
        for tx in transaction_list:
            key = tx.description.lower().strip()
            desc_groups[key].append(tx)

        # top 5 merchant clusters by spend
        top_descriptions = sorted(
            desc_groups.items(),
            key=lambda item: sum(t.amountInCents for t in item[1]),
            reverse=True
        )[:5]

        top_desc_list = [
            {
                "description": desc,
                "total": sum(t.amountInCents for t in txns),
                "count": len(txns)
            }
            for desc, txns in top_descriptions
        ]

        # ----------------------
        # Month time-series
        # ----------------------
        month_groups = defaultdict(list)
        for tx in transaction_list:
            month_key = tx.date.strftime("%Y-%m")
            month_groups[month_key].append(tx)

        month_totals = {
            month: sum(t.amountInCents for t in txns)
            for month, txns in month_groups.items()
        }

        # sort months chronologically: [('2024-01', x), ('2024-02', y)]
        sorted_months = sorted(month_totals.items(), key=lambda x: x[0])

        # month over month growth
        mom_growth = {}
        for i in range(1, len(sorted_months)):
            prev_month, prev_value = sorted_months[i - 1]
            curr_month, curr_value = sorted_months[i]
            if prev_value > 0:
                mom_growth[curr_month] = (curr_value - prev_value) / prev_value
            else:
                mom_growth[curr_month] = None

        # ----------------------
        # Concentration index
        # ----------------------
        # Herfindahl-Hirschman Index for spending diversity
        hhi = sum(p ** 2 for p in category_percentages.values())

        # ----------------------
        # Volatility (Coefficient of Variation)
        # ----------------------
        volatility = 0
        if len(month_totals) > 1:
            vals = list(month_totals.values())
            mean_val = statistics.mean(vals)
            if mean_val > 0:
                volatility = statistics.stdev(vals) / mean_val

        # ----------------------
        # Final structured result
        # ----------------------
        metrics = {
            "summary": {
                "totalSpend": total_spend,
                "transactionCount": count,
                "avgTransaction": avg_txn,
            },
            "categories": {
                "totals": category_totals,
                "percentages": category_percentages,
                "counts": category_counts,
            },
            "timeSeries": {
                "monthTotals": month_totals,
                "monthGrowth": mom_growth,
            },
            "advanced": {
                "concentrationIndex": hhi,
                "volatility": volatility,
            },
            "topMerchants": top_desc_list,
        }

        return metrics

    def _make_markdown_report_from_transaction_list(self, transaction_list: list['Transaction'], metrics: dict) -> str:

        vertexai_prompt = f"""
        You are a financial data analysis assistant.

        You will be given:
        1. A list of financial transactions.
        2. A dictionary of pre-computed metrics derived from these transactions.

        Your tasks are:

        (A) Display all provided metrics in a clean markdown report using well-structured tables.
            - Present metrics exactly as provided.
            - Do not recompute or invent values.
            - If a metric is missing, use “Not available”.

        (B) Generate short, conservative, data-backed insights based only on the provided metrics and transactions.
            - Insights must be strictly based on observed numerical patterns in the data.
            - If the data is insufficient for an insight, explicitly write: “Insufficient data”.
            - Do not speculate on the user’s behavior, motives, preferences, or intents.
            - Do not infer information that is not directly supported by the data.

        (C) Output format must be a **valid markdown string** that can be rendered as a full standalone report.

        Report Structure (strictly follow this order):

        # Financial Report

        ## Summary Metrics
        (Use a metrics table)

        ## Category Breakdown
        (Use a table showing category totals, counts, percentages if provided)

        ## Time-based Metrics
        (Use tables if time-based metrics exist, otherwise state: “Not available”)

        ## Insights
        - Bullet list of insights
        - Each insight must start with a clear observational fact.
        - No storytelling. No assumptions.

        Formatting Rules:
        - Prefer markdown tables for metrics.
        - Never fabricate or estimate numeric values.
        - Never describe trends that are not numerically proven.
        - Do not use speculative language (“may indicate”, “likely”, “probably”).

        Important:
        - The metrics provided are authoritative and correct. Do not attempt to recalculate them.
        - If a useful metric is not provided, do not create it yourself.
        - You may reference individual transactions only to support an insight (e.g., frequency, repetition), but do not summarize all transactions.

        Example safe insight pattern:
        - “Spending in the ‘Food’ category represents 26 percent of total spending. (Based on provided metrics)”

        Example unsafe patterns (disallowed):
        - “You like eating out a lot.”
        - “This trend suggests the user is traveling for work.”
        - “Probably spent money on vacation.”

        Your final response must contain **only the markdown report**, with no explanation of how you created it.

        """

        report_input = {
            "transactions": transaction_list,
            "metrics": metrics,
        }

        response = self.model.generate_content([
            {
                "role": "system",
                "content": vertexai_prompt
            },
            {
                "role": "user",
                "content": "Generate the financial report using the provided transaction data and metrics."
            },
            {
                "role": "model_input",
                "content": json.dumps(report_input)
            }
        ])

        return json.loads(response.text)

    def _upload_markdown_report_to_database(self, csv_id: int, markdown_report: str):
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO reports (csv_id, report_md)
                VALUES (%s, %s)
                RETURNING id
            """, (csv_id, markdown_report))
            report_id = cursor.fetchone()[0]
            logger.info(f"Markdown report uploaded successfully with report id: {report_id}")
        except Exception as e:
            logger.error(f"ReportMaker failed to upload report: {e}")
            if cursor:
                cursor.close()
            raise


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

