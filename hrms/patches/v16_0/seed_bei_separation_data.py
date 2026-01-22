# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Seed BEI DOLE Compliance Items and Exit Interview Questions"""
	seed_dole_compliance_items()
	seed_exit_interview_questions()


def seed_dole_compliance_items():
	"""Create DOLE compliance items for different separation types"""
	items = [
		{
			"item_code": "NTE-001",
			"description": "Notice to Explain (NTE) issued to employee with specific charges",
			"sla_days": 0,
			"dole_reference": "Labor Code Art. 297 (Twin-Notice Rule)",
			"applicable_types": ["Termination - Just Cause", "AWOL"],
		},
		{
			"item_code": "NTE-002",
			"description": "5-day response period observed after NTE",
			"sla_days": 5,
			"dole_reference": "Labor Code Art. 297 (Twin-Notice Rule)",
			"applicable_types": ["Termination - Just Cause", "AWOL"],
		},
		{
			"item_code": "NOR-001",
			"description": "Notice of Resolution (Decision Notice) issued",
			"sla_days": 0,
			"dole_reference": "Labor Code Art. 297 (Twin-Notice Rule)",
			"applicable_types": ["Termination - Just Cause", "AWOL"],
		},
		{
			"item_code": "DOLE-001",
			"description": "30-day advance notice filed with DOLE (Establishment Termination Report)",
			"sla_days": 30,
			"dole_reference": "Labor Code Art. 298 (Authorized Causes)",
			"applicable_types": ["Termination - Authorized Cause"],
		},
		{
			"item_code": "DOLE-002",
			"description": "30-day advance written notice to employee",
			"sla_days": 30,
			"dole_reference": "Labor Code Art. 298 (Authorized Causes)",
			"applicable_types": ["Termination - Authorized Cause"],
		},
		{
			"item_code": "SEP-001",
			"description": "Separation pay computed and released (1 month per year of service)",
			"sla_days": 30,
			"dole_reference": "Labor Code Art. 298",
			"applicable_types": ["Termination - Authorized Cause", "Retirement"],
		},
		{
			"item_code": "PROB-001",
			"description": "Standards/expectations communicated at hire (Day 1 documentation)",
			"sla_days": 0,
			"dole_reference": "Labor Code Art. 296 (Probationary Employment)",
			"applicable_types": ["Probation Failure"],
		},
		{
			"item_code": "PROB-002",
			"description": "Termination notice issued before end of probation period",
			"sla_days": 0,
			"dole_reference": "Labor Code Art. 296",
			"applicable_types": ["Probation Failure"],
		},
		{
			"item_code": "FP-001",
			"description": "Final pay released within 30 days from last day",
			"sla_days": 30,
			"dole_reference": "Labor Advisory No. 06-20",
			"applicable_types": [
				"Resignation",
				"Termination - Just Cause",
				"Termination - Authorized Cause",
				"AWOL",
				"Probation Failure",
				"End of Contract",
				"Retirement",
			],
		},
		{
			"item_code": "COE-001",
			"description": "Certificate of Employment issued within 3 days of request",
			"sla_days": 3,
			"dole_reference": "Labor Code Art. 313",
			"applicable_types": [
				"Resignation",
				"Termination - Just Cause",
				"Termination - Authorized Cause",
				"AWOL",
				"Probation Failure",
				"End of Contract",
				"Retirement",
			],
		},
		{
			"item_code": "AWOL-001",
			"description": "Return to Work Notice sent via registered mail",
			"sla_days": 0,
			"dole_reference": "DOLE-NLRC Jurisprudence",
			"applicable_types": ["AWOL"],
		},
		{
			"item_code": "AWOL-002",
			"description": "Proof of intent to abandon employment documented",
			"sla_days": 0,
			"dole_reference": "DOLE-NLRC Jurisprudence",
			"applicable_types": ["AWOL"],
		},
	]

	for item in items:
		if not frappe.db.exists("BEI DOLE Compliance Item", item["item_code"]):
			doc = frappe.new_doc("BEI DOLE Compliance Item")
			doc.item_code = item["item_code"]
			doc.description = item["description"]
			doc.sla_days = item["sla_days"]
			doc.dole_reference = item["dole_reference"]

			# Add applicable separation types
			for sep_type in item["applicable_types"]:
				doc.append(
					"applicable_separation_types",
					{"separation_type": sep_type},
				)

			doc.insert(ignore_permissions=True)

	frappe.db.commit()


def seed_exit_interview_questions():
	"""Create 26 standard exit interview questions"""
	questions = [
		# Recognition (4)
		{
			"category": "Recognition",
			"question_text": "Did you feel recognized for your contributions?",
			"response_type": "Scale 1-5",
			"display_order": 1,
		},
		{
			"category": "Recognition",
			"question_text": "Were your achievements acknowledged by your supervisor?",
			"response_type": "Scale 1-5",
			"display_order": 2,
		},
		{
			"category": "Recognition",
			"question_text": "Did you feel valued as a team member?",
			"response_type": "Scale 1-5",
			"display_order": 3,
		},
		{
			"category": "Recognition",
			"question_text": "Were rewards/incentives fairly distributed?",
			"response_type": "Scale 1-5",
			"display_order": 4,
		},
		# Growth (4)
		{
			"category": "Growth",
			"question_text": "Were you given opportunities to learn new skills?",
			"response_type": "Scale 1-5",
			"display_order": 5,
		},
		{
			"category": "Growth",
			"question_text": "Was there a clear career path for you?",
			"response_type": "Scale 1-5",
			"display_order": 6,
		},
		{
			"category": "Growth",
			"question_text": "Did you receive adequate training for your role?",
			"response_type": "Scale 1-5",
			"display_order": 7,
		},
		{
			"category": "Growth",
			"question_text": "Would you recommend BEI to someone starting their career?",
			"response_type": "Yes/No",
			"display_order": 8,
		},
		# Management (5)
		{
			"category": "Management",
			"question_text": "How would you rate your direct supervisor's leadership?",
			"response_type": "Scale 1-5",
			"display_order": 9,
		},
		{
			"category": "Management",
			"question_text": "Were expectations clearly communicated?",
			"response_type": "Scale 1-5",
			"display_order": 10,
		},
		{
			"category": "Management",
			"question_text": "Did you feel comfortable raising concerns to management?",
			"response_type": "Scale 1-5",
			"display_order": 11,
		},
		{
			"category": "Management",
			"question_text": "Was feedback given constructively and regularly?",
			"response_type": "Scale 1-5",
			"display_order": 12,
		},
		{
			"category": "Management",
			"question_text": "Did management handle conflicts fairly?",
			"response_type": "Scale 1-5",
			"display_order": 13,
		},
		# Culture (4)
		{
			"category": "Culture",
			"question_text": "Did you feel the workplace was safe and clean?",
			"response_type": "Scale 1-5",
			"display_order": 14,
		},
		{
			"category": "Culture",
			"question_text": "Was the team spirit positive?",
			"response_type": "Scale 1-5",
			"display_order": 15,
		},
		{
			"category": "Culture",
			"question_text": "Were company policies fair and consistently applied?",
			"response_type": "Scale 1-5",
			"display_order": 16,
		},
		{
			"category": "Culture",
			"question_text": "Would you consider returning to BEI in the future?",
			"response_type": "Yes/No",
			"display_order": 17,
		},
		# Compensation (3)
		{
			"category": "Compensation",
			"question_text": "Was your pay competitive for your role?",
			"response_type": "Scale 1-5",
			"display_order": 18,
		},
		{
			"category": "Compensation",
			"question_text": "Were benefits adequately explained and accessible?",
			"response_type": "Scale 1-5",
			"display_order": 19,
		},
		{
			"category": "Compensation",
			"question_text": "Was payroll always on time and accurate?",
			"response_type": "Scale 1-5",
			"display_order": 20,
		},
		# Store Operations (3 - BEI-specific)
		{
			"category": "Operations",
			"question_text": "Were store schedules fair and communicated in advance?",
			"response_type": "Scale 1-5",
			"display_order": 21,
		},
		{
			"category": "Operations",
			"question_text": "Did you have adequate equipment/supplies to do your job?",
			"response_type": "Scale 1-5",
			"display_order": 22,
		},
		{
			"category": "Operations",
			"question_text": "Was the workload manageable during peak hours?",
			"response_type": "Scale 1-5",
			"display_order": 23,
		},
		# Open-Ended (3)
		{
			"category": "Open-Ended",
			"question_text": "What is the primary reason you are leaving?",
			"response_type": "Text",
			"display_order": 24,
		},
		{
			"category": "Open-Ended",
			"question_text": "What could BEI have done differently to retain you?",
			"response_type": "Text",
			"display_order": 25,
		},
		{
			"category": "Open-Ended",
			"question_text": "Any other feedback you would like to share?",
			"response_type": "Text",
			"display_order": 26,
		},
	]

	for q in questions:
		# Check if question already exists by text
		existing = frappe.db.exists(
			"BEI Exit Interview Question",
			{"question_text": q["question_text"]},
		)
		if not existing:
			doc = frappe.new_doc("BEI Exit Interview Question")
			doc.category = q["category"]
			doc.question_text = q["question_text"]
			doc.response_type = q["response_type"]
			doc.display_order = q["display_order"]
			doc.active = 1
			doc.insert(ignore_permissions=True)

	frappe.db.commit()
