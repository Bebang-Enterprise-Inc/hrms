# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIInventorySpotCheckItem(Document):
	def before_save(self):
		# Auto-calculate variance
		if self.expected_count is not None and self.actual_count is not None:
			self.variance = self.actual_count - self.expected_count

		# Auto-set category based on item
		item_categories = {
			"Leche flan": "Highest Cost",
			"Frozen milk": "Highest Cost",
			"16OZ CUP WITH LOGO": "Single Count Variances",
			"DOME LID 90MM": "Single Count Variances",
			"LONG SPOON GREEN W/ POUCH": "Single Count Variances",
			"COCONUT JELLY": "Shortest Shelf Life",
			"COCONUT SYRUP": "Shortest Shelf Life",
			"Sago": "Most Used Items",
			"Buko pandan jelly": "Most Used Items",
			"Nata de coco": "Most Used Items",
			"SUNBEST WHOLE KETTLE CORN": "Most Used Items",
			"GOLDEN VALLEY WHOLE CORN": "Most Used Items",
		}
		if self.item_name in item_categories:
			self.category = item_categories[self.item_name]
