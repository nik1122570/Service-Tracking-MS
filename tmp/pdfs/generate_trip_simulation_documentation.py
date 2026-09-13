from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT = Path("output/pdf/trip_simulation_and_fuel_card_modality.pdf")


styles = getSampleStyleSheet()

styles.add(
	ParagraphStyle(
		name="CoverTitle",
		parent=styles["Title"],
		fontName="Helvetica-Bold",
		fontSize=24,
		leading=30,
		alignment=TA_CENTER,
		textColor=colors.HexColor("#0f172a"),
		spaceAfter=16,
	)
)
styles.add(
	ParagraphStyle(
		name="CoverSub",
		parent=styles["Normal"],
		fontSize=10.8,
		leading=15,
		alignment=TA_CENTER,
		textColor=colors.HexColor("#475569"),
		spaceAfter=7,
	)
)
styles.add(
	ParagraphStyle(
		name="H1",
		parent=styles["Heading1"],
		fontName="Helvetica-Bold",
		fontSize=15.5,
		leading=20,
		textColor=colors.HexColor("#12355b"),
		spaceBefore=10,
		spaceAfter=7,
	)
)
styles.add(
	ParagraphStyle(
		name="H2",
		parent=styles["Heading2"],
		fontName="Helvetica-Bold",
		fontSize=11.5,
		leading=15,
		textColor=colors.HexColor("#1e3a8a"),
		spaceBefore=8,
		spaceAfter=5,
	)
)
styles.add(
	ParagraphStyle(
		name="Body",
		parent=styles["BodyText"],
		fontSize=8.9,
		leading=12.6,
		textColor=colors.HexColor("#1f2937"),
		spaceAfter=5,
	)
)
styles.add(
	ParagraphStyle(
		name="Small",
		parent=styles["BodyText"],
		fontSize=7.8,
		leading=10.5,
		textColor=colors.HexColor("#475569"),
		spaceAfter=3,
	)
)
styles.add(
	ParagraphStyle(
		name="Formula",
		parent=styles["BodyText"],
		fontName="Helvetica-Bold",
		fontSize=8.4,
		leading=11.2,
		textColor=colors.HexColor("#111827"),
		spaceAfter=3,
	)
)
styles.add(
	ParagraphStyle(
		name="TableHeader",
		parent=styles["BodyText"],
		fontName="Helvetica-Bold",
		fontSize=7.7,
		leading=9.7,
		textColor=colors.white,
		alignment=TA_LEFT,
	)
)
styles.add(
	ParagraphStyle(
		name="Cell",
		parent=styles["BodyText"],
		fontSize=7.1,
		leading=9.2,
		textColor=colors.HexColor("#1f2937"),
		alignment=TA_LEFT,
	)
)
styles.add(
	ParagraphStyle(
		name="CellBold",
		parent=styles["BodyText"],
		fontName="Helvetica-Bold",
		fontSize=7.2,
		leading=9.3,
		textColor=colors.HexColor("#111827"),
		alignment=TA_LEFT,
	)
)
styles.add(
	ParagraphStyle(
		name="Note",
		parent=styles["BodyText"],
		fontSize=8.1,
		leading=11.2,
		leftIndent=6,
		borderPadding=7,
		borderColor=colors.HexColor("#bfdbfe"),
		borderWidth=0.7,
		backColor=colors.HexColor("#eff6ff"),
		textColor=colors.HexColor("#1e3a8a"),
		spaceBefore=3,
		spaceAfter=7,
	)
)


def p(text, style="Body"):
	return Paragraph(str(text), styles[style])


def cell(text, bold=False):
	return Paragraph(str(text), styles["CellBold" if bold else "Cell"])


def header(text):
	return Paragraph(str(text), styles["TableHeader"])


def make_table(rows, widths):
	data = [[header(c) for c in rows[0]]] + [
		[cell(c, i == 0) for i, c in enumerate(row)] for row in rows[1:]
	]
	table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
	table.setStyle(
		TableStyle(
			[
				("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12355b")),
				("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
				("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
				("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
				("VALIGN", (0, 0), (-1, -1), "TOP"),
				("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
				("LEFTPADDING", (0, 0), (-1, -1), 4.5),
				("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
				("TOPPADDING", (0, 0), (-1, -1), 4.5),
				("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
			]
		)
	)
	return table


def footer(canvas, doc):
	canvas.saveState()
	width, _height = A4
	canvas.setFont("Helvetica", 7.5)
	canvas.setFillColor(colors.HexColor("#64748b"))
	canvas.drawString(18 * mm, 11 * mm, "Service Tracking MS - Trip Simulation and Fuel Card Modality")
	canvas.drawRightString(width - 18 * mm, 11 * mm, f"Page {doc.page}")
	canvas.restoreState()


def build_story():
	story = []

	story.append(Spacer(1, 35 * mm))
	story.append(p("Trip Simulation and Fuel Card Modality", "CoverTitle"))
	story.append(p("Service Tracking MS - Functional Documentation", "CoverSub"))
	story.append(p(f"Prepared on {date.today().strftime('%d %B %Y')}", "CoverSub"))
	story.append(Spacer(1, 12 * mm))
	story.append(
		p(
			"This document explains how Trip Simulation estimates revenue, route cost, fuel quantity, "
			"fuel value, trip expenses, profit, and fuel card movements. It is intended for operations, "
			"finance, procurement, and system users."
		)
	)
	story.append(
		p(
			"Source areas reviewed: Trip Simulation, Trip Settings, Simulation Routes, Fixed Expenses, "
			"Fuel Card, Fuel Card Recharge, Fuel Card Issue, Fuel Card Ledger Entry, Project customer details, "
			"Quotation creation, Purchase Order creation, and Fuel Card Movement Report.",
			"Small",
		)
	)
	story.append(PageBreak())

	story.append(p("1. Executive Summary", "H1"))
	story.append(
		p(
			"Trip Simulation is the planning document used to estimate whether a trip is commercially viable "
			"before quotation and purchasing work begins. Users enter the expected revenue manually, select the "
			"route, vehicle, project, customer, fuel card, and supplier details, and the system calculates cost "
			"and margin."
		)
	)
	story.append(
		p(
			"After a Trip Simulation is submitted, the system can create a Quotation and Purchase Orders. "
			"If a Fuel Card is selected, submitting the simulation deducts the trip fuel litres and monetary "
			"value from that Fuel Card through a Fuel Card Ledger Entry.",
			"Note",
		)
	)

	story.append(p("2. Core Trip Simulation Formulas", "H1"))
	story.append(
		make_table(
			[
				["Area", "Formula", "Meaning / Source"],
				["Days in Trip", "Return Date - Departure Date + 1", "Inclusive day count. Saving is blocked if Return Date is before Departure Date."],
				["Total Distance (km)", "Sum of all Fuel table Distance rows", "Route distances are loaded from Simulation Routes trip steps into the Fuel child table."],
				["Fuel Used (Ltr)", "Distance x Truck Type Litres per KM", "Litres per KM comes from Trip Settings based on the selected Vehicle truck type."],
				["Total Fuel Used (Ltr)", "Sum of Fuel Used (Ltr) rows", "Stored as the total trip fuel quantity requirement."],
				["Fuel Price", "Latest purchase rate for Fuel Item", "Priority is submitted Purchase Invoice Item first, then submitted Purchase Order Item."],
				["Total Fuel Cost", "Total Fuel Used (Ltr) x Fuel Price", "Monetary value required from the Fuel Card or fuel procurement process."],
				["Total Trip Cost", "Total Fuel Cost + Sum of Trip Expenses Outline Amount", "Combines fuel and all calculated trip expense rows."],
				["Net Profit", "Expected Revenue - Total Trip Cost", "Expected Revenue is manually entered by the user."],
				["Net Profit Margin %", "Net Profit / Expected Revenue x 100", "Stored in net_profit_. If revenue is zero, margin becomes zero."],
			],
			[37 * mm, 58 * mm, 75 * mm],
		)
	)
	story.append(
		p(
			"Important: 100 - ((Expected Revenue - Total Trip Cost) / Expected Revenue) x 100 is a cost ratio. "
			"The system now uses Net Profit Margin: Net Profit / Expected Revenue x 100.",
			"Note",
		)
	)

	story.append(p("3. Trip Settings", "H1"))
	story.append(
		make_table(
			[
				["Setting", "Default / Type", "Used For"],
				["Management Fee Percentage", "3%", "Management Fee = Expected Revenue x Management Fee % / 100."],
				["Salaries Percentage", "10%", "Salaries = Expected Revenue x Salaries % / 100."],
				["Driver Mileage Per Day", "Currency, default 0", "Driver Mileage = Driver Mileage Per Day x Days in Trip."],
				["Heavy Truck Vehicle Cost", "85,000,000", "Depreciation for Heavy Truck vehicles."],
				["Light Truck Vehicle Cost", "45,000,000", "Depreciation for Light Truck vehicles."],
				["Heavy/Light Truck Tyre Price", "Currency", "Tyres formula by truck type."],
				["Heavy/Light Truck Number of Tyres", "Float", "Tyres formula by truck type."],
				["Heavy/Light Truck Tyre Lifecycle (km)", "Float", "Tyres formula by truck type."],
				["Heavy/Light Truck Litres per KM", "Float", "Fuel consumption formula by truck type."],
			],
			[46 * mm, 38 * mm, 86 * mm],
		)
	)
	story.append(
		p(
			"Trip Settings is a Single DocType. It stores the calculation constants centrally so users can "
			"change percentages, truck costs, tyre assumptions, fuel ratios, and driver mileage without editing code.",
			"Note",
		)
	)

	story.append(p("4. Expense Formulas", "H1"))
	story.append(
		make_table(
			[
				["Expense", "Formula", "Notes"],
				["Management Fee", "Expected Revenue x Management Fee % / 100", "Percentage is read from Trip Settings. Quantity stores the percentage; rate is Expected Revenue / 100."],
				["Salaries", "Expected Revenue x Salaries % / 100", "Percentage is read from Trip Settings. Default is 10%."],
				["Driver Mileage", "Driver Mileage Per Day x Days in Trip", "Daily amount is read from Trip Settings, not Fixed Expenses."],
				["Maintenance Fee", "Previous Month Maintenance Cost / 30 x Days in Trip", "Previous month maintenance cost is read from submitted Purchase Invoice Items linked to Purchase Orders and EAH Job Cards for the selected vehicle."],
				["Tyres", "Tyre Price x Number of Tyres / Tyre Lifecycle KM x Total Distance KM", "Tyre settings are read from Trip Settings by vehicle truck type. Tyres are exempt from route predefined amount restriction."],
				["Depreciation", "Vehicle Cost / Month Number / 12 / 30 x Days in Trip", "Vehicle Cost comes from Trip Settings by truck type. Month Number is the month number of the departure/transaction date."],
				["Per Trip Day", "Route Amount x Days in Trip", "Used for ordinary Fixed Expenses configured as Per Trip Day."],
				["Salary Allocation", "Salaries Constant / 30 / Active Vehicles x Days in Trip", "Legacy calculation method remains supported where configured."],
				["Percentage of Expected Revenue", "Expected Revenue x Expense % / 100", "Uses the percentage configured on Fixed Expenses or the row quantity."],
				["Fixed Amount", "Route Amount", "Used when no special calculation method applies."],
			],
			[36 * mm, 62 * mm, 72 * mm],
		)
	)

	story.append(p("5. Maintenance Cost Modality", "H1"))
	story.append(
		p(
			"Maintenance Fee uses actual maintenance history instead of a manually typed monthly constant. "
			"The system looks at the month before the trip reference date and sums submitted Purchase Invoice "
			"Item values that are linked to Purchase Orders. Those Purchase Orders must be linked to EAH Job Cards, "
			"and the EAH Job Card vehicle must match the Trip Simulation vehicle."
		)
	)
	story.append(p("Maintenance Fee = Previous Month Maintenance Cost / 30 x Days in Trip", "Formula"))
	story.append(
		p(
			"The Trip Expenses child table stores the previous month maintenance cost in a read-only field so users "
			"can see the source cost used by the formula and reports can expose it."
		)
	)

	story.append(p("6. Fuel Calculation Modality", "H1"))
	story.append(
		make_table(
			[
				["Step", "Calculation / Source", "Result"],
				["1", "Select Vehicle", "System identifies Vehicle truck type, for example Heavy Truck or Light Truck."],
				["2", "Read Trip Settings", "System gets the matching litres per KM field for that truck type."],
				["3", "Load Simulation Route", "Each route step distance is copied into the Fuel child table."],
				["4", "Calculate row litres", "Fuel Used (Ltr) = Distance x Litres per KM."],
				["5", "Calculate total litres", "Total Fuel Used (Ltr) = Sum of row fuel litres."],
				["6", "Fetch fuel price", "Last submitted Purchase Invoice Item rate for Fuel Item, else last submitted Purchase Order Item rate."],
				["7", "Calculate total fuel value", "Total Fuel Cost = Total Fuel Used (Ltr) x Fuel Price."],
			],
			[20 * mm, 72 * mm, 78 * mm],
		)
	)
	story.append(
		p(
			"Example: if a Heavy Truck uses 0.300 litres per KM and the route distance is 572 KM, "
			"Total Fuel Used = 572 x 0.300 = 171.6 litres.",
			"Note",
		)
	)

	story.append(p("7. Fuel Card Modality", "H1"))
	story.append(
		p(
			"The Fuel Card feature models prepaid fuel. Procurement can recharge a card with litres and value, "
			"while trips and other fuel issues consume litres and value. The Fuel Card Ledger Entry is the source "
			"of truth for all balance movements."
		)
	)
	story.append(
		make_table(
			[
				["Transaction", "Movement", "Formula / Control"],
				["Fuel Card Opening Balance", "Initial litres and value", "Stored on Fuel Card as opening_litres and opening_value."],
				["Recharge", "Litres In", "Amount = Litres x Rate. On submit, creates a Recharge ledger entry."],
				["Trip Usage", "Litres Out", "On Trip Simulation submit, Total Fuel Used is deducted at Fuel Price."],
				["Other Issue", "Litres Out", "Fuel Card Issue handles office car or non-simulation fuel usage. Amount = Litres x Rate."],
				["Cancellation of Recharge", "Litres Out", "Cancelling a recharge creates a reversing Cancellation entry."],
				["Cancellation of Issue / Trip", "Litres In", "Cancelling an issue or simulation creates a reversing Cancellation entry."],
			],
			[42 * mm, 38 * mm, 90 * mm],
		)
	)
	story.append(p("Ledger Amount = Litres In or Litres Out x Rate", "Formula"))
	story.append(p("Balance Litres After Transaction = Previous Balance + Litres In - Litres Out", "Formula"))
	story.append(p("Balance Value After Transaction = Previous Value + Value In - Value Out", "Formula"))
	story.append(
		p(
			"The system blocks a ledger entry if it would make the card litres negative or the monetary value negative. "
			"For Trip Simulation, this means a trip cannot consume more fuel value than the selected Fuel Card has available. "
			"Users are asked to refill the Fuel Card."
		)
	)

	story.append(p("8. Fuel Card Dashboard on Trip Simulation", "H1"))
	story.append(
		p(
			"When a Fuel Card is selected in Trip Simulation, the form shows a fuel card status area. It compares the "
			"requested trip fuel amount against the current Fuel Card balance. This helps the user know whether the trip "
			"can be submitted or whether the card should be recharged first."
		)
	)
	story.append(
		make_table(
			[
				["Dashboard Value", "Meaning"],
				["Card Balance Litres", "Current available litres from opening balance plus ledger movements."],
				["Card Balance Value", "Current available monetary value from opening value plus ledger movements."],
				["Requested Litres", "Trip Simulation Total Fuel Used (Ltr)."],
				["Requested Amount", "Total Fuel Used (Ltr) x Fuel Price."],
				["Availability Status", "Shows whether the selected card has enough monetary value for the trip."],
			],
			[55 * mm, 115 * mm],
		)
	)

	story.append(p("9. Document Creation and Linkage", "H1"))
	story.append(
		make_table(
			[
				["Document", "When Created", "Linkage"],
				["Quotation", "After Trip Simulation is submitted using Create Quotation", "Quotation stores custom_trip_simulation where the custom field exists; Trip Simulation stores the Quotation reference."],
				["Fuel Purchase Order", "After Trip Simulation is submitted using Create Purchase Order for fuel", "Purchase Order stores custom_trip_simulation and custom_vehicle where fields exist; Trip Simulation stores fuel_purchase_order."],
				["Expense Purchase Order", "For selected payable expenses", "Only Fixed Expenses marked Is Payable can be converted to Purchase Order items."],
				["Fuel Card Ledger Entry", "Automatically on submit/cancel", "Trip Simulation stores fuel_card_ledger_entry for the submit deduction."],
			],
			[43 * mm, 58 * mm, 69 * mm],
		)
	)

	story.append(p("10. Project Customer Details", "H1"))
	story.append(
		p(
			"The Project form contains Customer Details used by the Trip Simulation and quotation flow. These include "
			"Customer, Route, Sales Order, Rate per trip, Sales Item, Driver Mileage per Trip, Fuel Entitlement Per Trip, "
			"Fuel Item, and Mileage Item."
		)
	)
	story.append(
		p(
			"Sales Item is especially important for Create Quotation. Trip Simulation uses Expected Revenue as the Quotation "
			"rate, but the item code is read from Project Sales Item."
		)
	)

	story.append(p("11. Controls and Validations", "H1"))
	story.append(
		make_table(
			[
				["Control", "Behavior"],
				["Targeted Net Profit", "Saving/submitting is blocked when Net Profit Margin is below Targeted Net Profit."],
				["Duplicate Expenses", "Duplicate expense rows are blocked after normalizing labels with trim/lowercase and standard labels."],
				["Route Expense Limits", "Expenses cannot exceed their route predefined amount, except Tyres."],
				["Custom Expenses", "Route expense labels are stored as data so operational custom labels can be added, but payable purchase orders still require matching Fixed Expenses with an Item."],
				["Fuel Price", "Trip Fuel Card deduction requires Fuel Price greater than zero."],
				["Fuel Card Balance", "Ledger entries are blocked if litres or monetary balance would become negative."],
				["Ledger Integrity", "Fuel Card Ledger Entry cannot be deleted; users must create reversing entries."],
				["Submitted Document Cleanliness", "Post-submit link updates use db_set/db_set_value with update_modified=False where needed to avoid unnecessary Not Saved state."],
			],
			[45 * mm, 125 * mm],
		)
	)

	story.append(p("12. Reports and Workspace", "H1"))
	story.append(
		make_table(
			[
				["Area", "Shows"],
				["Trip Simulation Center Workspace", "Number cards for simulations, revenue, cost, profit/loss, fuel card balance litres, and fuel card balance value."],
				["Workspace Charts", "Revenue vs Cost vs Profit/Loss chart and Trip Cost Breakdown pie chart."],
				["Trip Analysis Report", "Columns include revenue, total trip cost, fuel cost, fuel litres, expense breakdown, net profit, net margin, and margin variance."],
				["Fuel Card Movement Report", "Recharge, trip usage, other issues, rate, litres in/out, amount, and running balances."],
			],
			[48 * mm, 122 * mm],
		)
	)

	story.append(p("13. Quick Formula Reference", "H1"))
	for formula in [
		"Days in Trip = Return Date - Departure Date + 1",
		"Fuel Used (Ltr) = Distance KM x Truck Type Litres per KM",
		"Total Fuel Cost = Total Fuel Used (Ltr) x Fuel Price",
		"Management Fee = Expected Revenue x Management Fee % / 100",
		"Salaries = Expected Revenue x Salaries % / 100",
		"Driver Mileage = Driver Mileage Per Day x Days in Trip",
		"Maintenance Fee = Previous Month Maintenance Cost / 30 x Days in Trip",
		"Tyres = Tyre Price x Number of Tyres / Tyre Lifecycle KM x Total Distance KM",
		"Depreciation = Vehicle Cost / Month Number / 12 / 30 x Days in Trip",
		"Total Trip Cost = Total Fuel Cost + Sum of Trip Expense Amounts",
		"Net Profit = Expected Revenue - Total Trip Cost",
		"Net Profit Margin % = Net Profit / Expected Revenue x 100",
		"Fuel Card Amount = Litres x Rate",
		"Fuel Card Litres Balance = Opening Litres + Sum(Litres In - Litres Out)",
		"Fuel Card Value Balance = Opening Value + Sum((Litres In - Litres Out) x Rate)",
	]:
		story.append(p(formula, "Formula"))

	return story


def main():
	OUTPUT.parent.mkdir(parents=True, exist_ok=True)
	doc = SimpleDocTemplate(
		str(OUTPUT),
		pagesize=A4,
		rightMargin=18 * mm,
		leftMargin=18 * mm,
		topMargin=17 * mm,
		bottomMargin=18 * mm,
		title="Trip Simulation and Fuel Card Modality",
		author="Service Tracking MS",
	)
	doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
	print(OUTPUT)


if __name__ == "__main__":
	main()
