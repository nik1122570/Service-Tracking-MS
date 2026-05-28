# Trip Simulation Process Documentation

## 1. Purpose

The Trip Simulation process helps management estimate the profitability of a planned logistics trip before the trip is executed. It combines route setup, fuel consumption, fixed expenses, revenue, and payable costs into one simulation document.

The process supports:

- Route-based cost planning
- Automated trip expense extraction
- Fuel cost calculation
- Gross profit and gross profit percentage analysis
- Purchase Order creation for payable trip expenses
- Purchase Order creation for fuel
- Traceability between Trip Simulation and Purchase Orders
- Management reporting through the Trip Analysis Report

## 2. Process Overview

The process follows this sequence:

1. Set up Fixed Expenses.
2. Set up Simulation Routes.
3. Create a Trip Simulation.
4. Select a route and allow the system to populate route details.
5. Enter revenue and trip-specific inputs.
6. Review total costs and profitability.
7. Submit the Trip Simulation.
8. Create Purchase Orders for payable expenses.
9. Create Purchase Order for fuel.
10. Review performance using the Trip Analysis Report.

## 3. Fixed Expenses Setup

Fixed Expenses are the master records used to define standard cost items that may appear in trip simulations.

Examples include:

- Driver Mileage
- Salaries
- Depreciation
- Management Fee
- Tyres
- Car Wash
- Maintenance Fee

Each Fixed Expense can define:

- Expense name
- Fixed value or rate
- Currency
- Calculation method
- Whether the expense is payable
- Item to use when creating a Purchase Order

### 3.1 Calculation Methods

The system supports both fixed and formula-based expenses.

If no calculation method is selected, the system treats the expense as a fixed amount.

Supported automated calculation methods include:

| Calculation Method | Formula | Example Use |
|---|---|---|
| Per Trip Day | Fixed rate x Days in Trip | Driver Mileage |
| Salary Allocation | Salaries / 30 / Active Vehicles x Days in Trip | Salaries |
| Vehicle Depreciation | Vehicle Costs / Current Month Number / 12 / 30 x Days in Trip | Depreciation |

### 3.2 Payable Expenses

The `Is Payable` checkbox controls whether an expense can be converted into a Purchase Order.

Examples:

- Payable: Driver Mileage, Maintenance Fee, Tyres, Car Wash
- Not Payable: Salaries, Depreciation, Management Fee

Only payable expenses appear in the Purchase Order selection dialog.

## 4. Simulation Routes Setup

Simulation Routes define the standard route and expected route costs.

A route includes:

- Starting Point
- Ending Point
- Route Steps
- Fixed Expenses

### 4.1 Route Steps

Route Steps define the movement legs of the trip.

Each row includes:

- Loading Location
- Unloading Location
- Distance in Kilometers
- Fuel Consumption Quantity

The system automatically sums:

- Total Distance
- Total Fuel Consumption Quantity

These route totals are used later in the Trip Simulation.

### 4.2 Fixed Expenses in Simulation Routes

When a Simulation Route is created, the standard fixed expenses are automatically available in the route.

The system fetches the expense amount from the Fixed Expenses master. Users may add additional logistics-related expenses where required.

Controls applied in Simulation Routes:

- Duplicate expenses are not allowed.
- Standard route expenses are available by default.
- Amounts are based on the Fixed Expenses master.

## 5. Trip Simulation Creation

The Trip Simulation is used to calculate the estimated performance of a specific planned trip.

Important fields include:

- Transaction Date
- Project
- Route
- Driver
- Vehicle
- Cost Center
- Departure Date
- Return Date
- Days in Trip
- Expected Revenue
- Fuel Supplier
- Fuel Item
- Fuel Price
- Salaries
- Vehicle Costs
- Active Vehicles

### 5.1 Route Selection

When the user selects a Route, the system fetches data from the Simulation Route.

The system automatically populates:

- Fuel route steps
- Total distance
- Total fuel consumption quantity
- Trip expense outline
- Fixed expense amounts and calculated values

This reduces manual entry and ensures the Trip Simulation follows the approved route costing structure.

### 5.2 Days in Trip

Days in Trip is calculated automatically using:

```text
Return Date - Departure Date + 1
```

Example:

If Departure Date is 28 May and Return Date is 31 May:

```text
31 May - 28 May + 1 = 4 days
```

The value is used by formulas such as Driver Mileage, Salary Allocation, and Depreciation.

## 6. Fuel Cost Calculation

Fuel is calculated from route fuel consumption and fuel price.

Formula:

```text
Total Fuel Costs = Total Fuel Consumption Quantity x Fuel Price
```

Example:

```text
Total Fuel Consumption Quantity = 184 litres
Fuel Price = 4,000
Total Fuel Costs = 184 x 4,000 = 736,000
```

The fuel cost is included in the Total Trip Cost.

## 7. Trip Expense Calculations

Trip expenses are populated into the Trip Expenses Outline table.

The system supports both fixed and calculated expenses.

### 7.1 Driver Mileage

Driver Mileage uses the `Per Trip Day` calculation method.

Formula:

```text
Driver Mileage = Fixed Per Diem x Days in Trip
```

Example:

```text
80,000 x 4 days = 320,000
```

### 7.2 Salaries

Salaries use the `Salary Allocation` calculation method.

Formula:

```text
Salaries / 30 / Active Vehicles x Days in Trip
```

This allocates salary cost fairly across active vehicles and trip days.

### 7.3 Depreciation

Depreciation uses the `Vehicle Depreciation` calculation method.

Formula:

```text
Vehicle Costs / Current Month Number / 12 / 30 x Days in Trip
```

The current month number is automatically derived from the Departure Date. If Departure Date is not available, the system uses the Transaction Date.

Example:

For May, the month number is 5.

### 7.4 Fixed Amount Expenses

If an expense has no calculation method, the system uses the fixed amount defined in the route or Fixed Expenses master.

Formula:

```text
Expense Amount = Fixed Amount
```

## 8. Total Trip Cost

Total Trip Cost combines fuel and all trip expenses.

Formula:

```text
Total Trip Cost = Total Fuel Costs + Sum of Trip Expense Amounts
```

This gives management the estimated full cost of performing the trip.

## 9. Gross Profit Calculation

Gross Profit Amount shows the expected profit or loss in currency value.

Formula:

```text
Gross Profit Amount = Expected Revenue - Total Trip Cost
```

Gross Profit Percentage shows the profit or loss as a percentage of revenue.

Formula:

```text
Gross Profit % = Gross Profit Amount / Expected Revenue x 100
```

Example:

```text
Expected Revenue = 400,000
Total Trip Cost = 1,675,630
Gross Profit Amount = 400,000 - 1,675,630 = -1,275,630
Gross Profit % = -1,275,630 / 400,000 x 100 = -318.91%
```

This helps management quickly identify profitable and loss-making routes or trips.

## 10. Revenue Entry and Extraction

The Expected Revenue is entered in the Trip Simulation.

The system uses Expected Revenue to calculate:

- Gross Profit Amount
- Gross Profit Percentage
- Revenue vs Cost comparison in the Trip Analysis Report

The revenue value becomes the basis for management analysis and trip profitability review.

## 11. Controls in Trip Simulation

The system applies several controls to protect the costing process.

### 11.1 Duplicate Expense Control

The same expense cannot be added more than once in the Trip Expenses Outline.

Example:

Depreciation cannot appear twice in the same Trip Simulation.

### 11.2 Route Expense Limit Control

Trip expenses cannot exceed the predefined amount or calculated limit from the selected Simulation Route.

This prevents users from over-expensing trips beyond approved route rates.

### 11.3 Payable Expense Control

Only expenses marked as payable in Fixed Expenses can be converted into Purchase Orders.

### 11.4 Duplicate Purchase Order Control

Once an expense row has been used to create a Purchase Order, it is linked to that Purchase Order and no longer appears in the payable expense selection dialog.

If all payable trip expenses have already been converted into Purchase Orders, the system displays:

```text
All Trip Expenses Paid
```

## 12. Purchase Orders for Trip Expenses

After the Trip Simulation is submitted, the user can create Purchase Orders for payable trip expenses.

### 12.1 Expense Purchase Order Process

1. Open a submitted Trip Simulation.
2. Click `Create Purchase Order`.
3. Select one or more payable expenses.
4. The system creates a Purchase Order using the selected expenses.
5. The created Purchase Order is linked back to the Trip Simulation.
6. Each expense row is marked with the Purchase Order reference.

### 12.2 Purchase Order Mapping for Expenses

The system maps the following values:

| Trip Simulation Field | Purchase Order Field |
|---|---|
| Supplier | Supplier |
| Project | Project |
| Cost Center | Cost Center |
| Vehicle | Vehicle |
| Trip Simulation | Trip Simulation Reference |

For each Purchase Order Item:

| Trip Expense Field | Purchase Order Item Field |
|---|---|
| Expense Item | Item |
| Quantity | Quantity |
| Rate | Rate |
| Description | Description |
| Project | Project |
| Cost Center | Cost Center |
| Vehicle | Vehicle |

### 12.3 Expense PO Traceability

Traceability is maintained in both directions:

- The Trip Simulation expense row shows the created Purchase Order.
- The Purchase Order shows the originating Trip Simulation.

This supports audit review and prevents duplicate procurement for the same cost.

## 13. Purchase Orders for Fuel

Fuel is purchased separately because fuel uses a different supplier and item setup.

### 13.1 Fuel Purchase Order Process

1. Open a submitted Trip Simulation.
2. Go to the Fuel Costs section.
3. Confirm Fuel Supplier is set.
4. Confirm Fuel Item is set.
5. Confirm Total Fuel Consumption Quantity and Fuel Price are available.
6. Click `Create Purchase Order` next to the Fuel Supplier field.
7. The system creates a Fuel Purchase Order.
8. The Fuel Purchase Order is linked back to the Trip Simulation.

### 13.2 Fuel Purchase Order Formula

Fuel Purchase Order quantity and rate are taken from the Trip Simulation.

```text
PO Quantity = Total Fuel Consumption Quantity
PO Rate = Fuel Price
PO Amount = PO Quantity x PO Rate
```

### 13.3 Fuel Purchase Order Mapping

| Trip Simulation Field | Purchase Order Field |
|---|---|
| Fuel Supplier | Supplier |
| Fuel Item | Item |
| Total Fuel Consumption Quantity | Quantity |
| Fuel Price | Rate |
| Project | Project |
| Cost Center | Cost Center |
| Vehicle | Vehicle |
| Trip Simulation | Trip Simulation Reference |

### 13.4 Fuel PO Duplicate Control

The system stores the created Fuel Purchase Order in the `Fuel Purchase Order` field.

If a Fuel Purchase Order already exists, the system prevents creating another one for the same Trip Simulation.

## 14. Trip Analysis Report

The Trip Analysis Report gives management a summarized view of trip profitability.

The report shows:

- Trip
- Transaction Date
- Route
- Project
- Vehicle
- Revenue of the Trip
- Total Trip Costs
- Total Fuel Costs
- Gross Profit Amount
- Gross Profit Percentage
- Departure Date
- Return Date
- Days in Trip
- Cost Center

### 14.1 Report Filters

Management can filter by:

- From Date
- To Date
- Project
- Route
- Vehicle
- Cost Center
- Document Status

### 14.2 Line Graph

The report includes a line graph comparing:

- Revenue of the Trip
- Total Trip Cost

This graph helps management see whether trip costs are above or below expected revenue across multiple trips.

## 15. Management Benefits

The Trip Simulation process gives management:

- Better visibility before committing to a trip
- Standardized route costing
- Reduced manual calculation errors
- Controlled expense limits
- Prevention of duplicate expenses
- Prevention of duplicate Purchase Orders
- Clear link between simulation, cost, and procurement
- Route and vehicle profitability analysis
- Better decision-making on whether a trip should proceed

## 16. Recommended Operating Procedure

1. Maintain Fixed Expenses regularly.
2. Review and approve Simulation Route rates.
3. Create Trip Simulation before trip execution.
4. Select route and verify auto-filled costs.
5. Enter expected revenue and trip-specific values.
6. Review gross profit amount and gross profit percentage.
7. Submit only after management or operations approval.
8. Create Purchase Orders only for approved payable expenses.
9. Create Fuel Purchase Order from the Fuel Costs section.
10. Use Trip Analysis Report for management review.

## 17. Key Governance Notes

- Fixed Expenses should be maintained by authorized users only.
- Route rates should be reviewed whenever operational costs change.
- Payable and non-payable expense classification should be controlled.
- Purchase Orders should only be created from submitted Trip Simulations.
- Any loss-making trip should be reviewed before execution or approval.
- The Trip Analysis Report should be reviewed periodically by management.
