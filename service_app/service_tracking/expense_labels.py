STANDARD_FIXED_EXPENSES = (
	"Driver Mileage",
	"Salaries",
	"Car Wash",
	"Maintenance Fee",
	"Depreciation",
	"Management Fee",
	"Tyres",
)


def normalize_expense_name(expense):
	return " ".join((expense or "").strip().lower().split())


STANDARD_FIXED_EXPENSE_BY_KEY = {
	normalize_expense_name(expense): expense for expense in STANDARD_FIXED_EXPENSES
}


def canonical_expense_label(expense):
	return STANDARD_FIXED_EXPENSE_BY_KEY.get(normalize_expense_name(expense), (expense or "").strip())
