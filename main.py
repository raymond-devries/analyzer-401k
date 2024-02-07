import pandas as pd
from bokeh.models import NumeralTickFormatter, HoverTool
from bokeh.plotting import figure
import panel as pn

pd.options.display.max_columns = None
pd.options.display.float_format = "{:20,.2f}".format

YEAR = "Year"
GROSS_INCOME = "Gross Income (-SD)"
TAXABLE_INCOME = "Taxable Income"
CONTRIBUTION_401K = "401k Contribution"
TOTAL_CONTRIBUTIONS_401K = "Total 401k Contributions"
ROTH_401K_BALANCE = "Roth 401k Balance"
TRADITIONAL_401K_BALANCE = "Traditional 401k Balance"
TAX_WITH_NO_401K_DEDUCTION = "Tax With No 401k Deduction"
TAX_AFTER_DEDUCTIONS = "Tax After Deductions"
TOTAL_SAVED_TAX_INVESTED = "Total Saved Tax Invested"
TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST = "Total Saved Tax Invested (Plus Interest)"
TOTAL_INVESTMENT = "Total Investment"
STANDARD_DEDUCTION = "Standard Deduction"
TRADITIONAL_DISTRIBUTION = "Traditional Distribution"
TOTAL_TRADITIONAL_DISTRIBUTION = "Total Traditional Distribution"
DISTRIBUTION_TAXES = "Distribution Taxes"
TOTAL_DISTRIBUTION_TAXES = "Total Distribution Taxes"
ROTH_DISTRIBUTION = "Roth Distribution"
TOTAL_ROTH_DISTRIBUTION = "Total Roth Distribution"

COLOR_EBONY = "#503d3f"
COLOR_JADE = "#44AF69"
COLOR_COSMIC_LATTE = "#F7F3E3"
COLOR_ORANGE = "#E36414"
COLOR_MIDNIGHT_GREEN = "#0F4C5C"


# Define tax brackets and rates for USA 2024
DEFAULT_TAX_BRACKETS = [
    (0, 11600),
    (11600, 47150),
    (47150, 100525),
    (100525, 191951),
    (191951, 243725),
    (243725, 578125),
    (609351, float("inf")),
]
DEFAULT_TAX_RATES = [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]


def calculate_compound_interest(principal, interest_rate, years):
    return principal * ((1 + interest_rate) ** years)


# Function to calculate tax based on income
def calculate_tax(income, tax_brackets, inflation=0, years=0):
    tax = 0
    for (low, high), rate in tax_brackets:
        low = calculate_compound_interest(low, inflation, years)
        high = calculate_compound_interest(high, inflation, years)
        if income <= low:
            break
        elif income > high:
            tax += (high - low) * rate
        else:
            tax += (income - low) * rate
            break
    return tax


def build_tax_brackets(tax_brackets, tax_rates):
    brackets_and_rates = sorted(zip(tax_brackets, tax_rates), key=lambda x: x[0][1])
    dependencies = []
    inputs = []
    for (low, high), rate in brackets_and_rates:
        if high == float("inf"):
            anything_above_input = pn.widgets.IntInput(name="Anything Above", sizing_mode="stretch_width", value=low)
            rate_input = pn.widgets.IntInput(name="Rate %", sizing_mode="stretch_width", value=int(rate * 100))
            dependencies.extend([anything_above_input, rate_input])
            inputs.append(pn.Row(anything_above_input, rate_input))
        else:
            up_to_input = pn.widgets.FloatInput(name="Up to", sizing_mode="stretch_width", value=high)
            rate_input = pn.widgets.IntInput(name="Rate %", sizing_mode="stretch_width", value=int(rate * 100))
            dependencies.extend([up_to_input, rate_input])
            inputs.append(pn.Row(up_to_input, rate_input))

    return inputs, dependencies


def parse_tax_brackets(tax_bracket_column: pn.Column, *dependencies):
    tax_brackets = []
    rates = []
    up_to_brackets = tax_bracket_column.objects[:-1]
    for bracket in up_to_brackets:
        low_value = tax_brackets[-1][1] if tax_brackets else 0
        high_value = bracket.objects[0].value
        rate = bracket.objects[1].value / 100
        tax_brackets.append((low_value, high_value))
        rates.append(rate)

    last_bracket = tax_bracket_column.objects[-1]
    low_value = last_bracket.objects[0].value
    rate = last_bracket.objects[1].value / 100
    tax_brackets.append((low_value, float("inf")))
    rates.append(rate)
    return tuple(zip(tuple(tax_brackets), tuple(rates)))


def set_compound_interest(df, principal_col, earned_column, interest_rate):
    if earned_column != principal_col:
        df[earned_column] = [float(0)] * len(df)
    df.loc[0, earned_column] = float(df.loc[0, principal_col] * (1 + interest_rate))
    for i in range(1, len(df)):
        df.loc[i, earned_column] = float(
            (df.loc[i - 1, earned_column] + df.loc[i, principal_col] - df.loc[i - 1, principal_col])
            * (1 + interest_rate)
        )


@pn.cache
def build_df(
    years,
    standard_deduction,
    gross_income,
    yearly_contribution,
    yearly_raise,
    traditional_percent,
    interest_rate,
    tax_brackets_info,
    inflation,
    **__,
):
    traditional_percent = traditional_percent / 100
    interest_rate = interest_rate / 100
    inflation = inflation / 100

    df = pd.DataFrame(index=range(years))
    df[YEAR] = df.index + 1

    df[CONTRIBUTION_401K] = float(yearly_contribution) * ((1 + inflation) ** df[YEAR])
    df[TOTAL_CONTRIBUTIONS_401K] = df[CONTRIBUTION_401K].cumsum()

    set_compound_interest(df, TOTAL_CONTRIBUTIONS_401K, ROTH_401K_BALANCE, interest_rate)
    df[TRADITIONAL_401K_BALANCE] = df[ROTH_401K_BALANCE] * traditional_percent
    df[ROTH_401K_BALANCE] = df[ROTH_401K_BALANCE] * (1 - traditional_percent)

    df[STANDARD_DEDUCTION] = float(standard_deduction) * ((1 + inflation) ** df[YEAR])

    df[GROSS_INCOME] = gross_income + (df[YEAR] * yearly_raise) - df[STANDARD_DEDUCTION]
    df[TAXABLE_INCOME] = df[GROSS_INCOME] - (traditional_percent * yearly_contribution)
    df[TAX_WITH_NO_401K_DEDUCTION] = df.apply(
        lambda row: calculate_tax(row[GROSS_INCOME], tax_brackets_info, inflation, row[YEAR]), axis=1
    )
    df[TAX_AFTER_DEDUCTIONS] = df.apply(
        lambda row: calculate_tax(row[TAXABLE_INCOME], tax_brackets_info, inflation, row[YEAR]), axis=1
    )

    df[TOTAL_SAVED_TAX_INVESTED] = (df[TAX_WITH_NO_401K_DEDUCTION] - df[TAX_AFTER_DEDUCTIONS]).cumsum()
    set_compound_interest(df, TOTAL_SAVED_TAX_INVESTED, TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST, interest_rate)

    df[TOTAL_INVESTMENT] = (
        df[TRADITIONAL_401K_BALANCE] + df[ROTH_401K_BALANCE] + df[TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST]
    )

    return df


@pn.cache
def build_distribution_df(
    distribution_years, yearly_distributions, retirement_interest_rate, inflation, tax_brackets_info, **kwargs
):
    results_df = build_df(inflation=inflation, tax_brackets_info=tax_brackets_info, **kwargs)
    years = results_df[YEAR].iloc[-1]
    roth_final = results_df[ROTH_401K_BALANCE].iloc[-1]
    traditional_final = results_df[TRADITIONAL_401K_BALANCE].iloc[-1]
    retirement_interest_rate = retirement_interest_rate / 100
    extra_final = results_df[TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST].iloc[-1]

    roth_pct = roth_final / (traditional_final + roth_final)
    traditional_pct = traditional_final / (traditional_final + roth_final)
    inflation = inflation / 100

    df = pd.DataFrame(index=range(distribution_years))
    df[YEAR] = df.index + years
    df[ROTH_DISTRIBUTION] = roth_pct * yearly_distributions
    df[TOTAL_ROTH_DISTRIBUTION] = df[ROTH_DISTRIBUTION].cumsum()

    df[ROTH_401K_BALANCE] = roth_final - df[ROTH_DISTRIBUTION] * (df.index + 1)
    set_compound_interest(df, ROTH_401K_BALANCE, ROTH_401K_BALANCE, retirement_interest_rate)

    df[TRADITIONAL_DISTRIBUTION] = traditional_pct * yearly_distributions
    df[TOTAL_TRADITIONAL_DISTRIBUTION] = df[TRADITIONAL_DISTRIBUTION].cumsum()
    df[DISTRIBUTION_TAXES] = df.apply(
        lambda row: calculate_tax(row[TRADITIONAL_DISTRIBUTION], tax_brackets_info, inflation, row[YEAR]), axis=1
    )
    df[TOTAL_DISTRIBUTION_TAXES] = df[DISTRIBUTION_TAXES].cumsum()

    df[TRADITIONAL_401K_BALANCE] = traditional_final - df[TRADITIONAL_DISTRIBUTION] * (df.index + 1)
    set_compound_interest(df, TRADITIONAL_401K_BALANCE, TRADITIONAL_401K_BALANCE, retirement_interest_rate)
    return df


def build_tax_graph(tax_saved, tax_incurred_during_distributions):
    x = ["Tax Saved (Plus Interest Earned)", "Tax During Distributions"]
    p = figure(title="Taxes", sizing_mode="stretch_both", min_height=300, x_range=x)

    top = [tax_saved, tax_incurred_during_distributions]
    p.vbar(x=x, top=top, width=0.4, color=[COLOR_MIDNIGHT_GREEN, COLOR_ORANGE])

    hover = HoverTool(tooltips=[("", "@x"), ("Amount", "@top{($ 0.00 a)}")], mode="vline")
    p.add_tools(hover)

    p.yaxis[0].formatter = NumeralTickFormatter(format="$ 0.00 a")
    # p.legend.location = "top_left"
    return p


def build_income_graph(df):
    p = figure(title="Income", x_axis_label="Year", sizing_mode="stretch_both", min_height=600)
    years = df[YEAR]
    roth = df[ROTH_401K_BALANCE]
    traditional = df[TRADITIONAL_401K_BALANCE]
    extra = df[TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST]
    total_investment = df[TOTAL_INVESTMENT]
    p.line(years.values, roth.values, line_color=COLOR_JADE, legend_label="Roth 401k")
    p.line(years.values, traditional.values, line_color=COLOR_ORANGE, legend_label="Traditional 401k")
    p.line(years.values, extra.values, line_color=COLOR_MIDNIGHT_GREEN, legend_label="Extra Earned")
    p.line(years.values, total_investment.values, line_color=COLOR_EBONY, legend_label=TOTAL_INVESTMENT)

    circle_size = 5
    p.circle(years.values, roth.values, color=COLOR_JADE, legend_label="Roth 401k", size=circle_size)
    p.circle(years.values, traditional.values, color=COLOR_ORANGE, legend_label="Traditional 401k", size=circle_size)
    p.circle(years.values, extra.values, color=COLOR_MIDNIGHT_GREEN, legend_label="Extra Earned", size=circle_size)
    p.circle(
        years.values,
        total_investment.values,
        color=COLOR_EBONY,
        legend_label=TOTAL_INVESTMENT,
        size=circle_size,
    )

    hover = HoverTool(tooltips=[("Year", "@x"), ("Value", "@y{($ 0.00 a)}")], mode="vline")
    p.add_tools(hover)

    p.yaxis[0].formatter = NumeralTickFormatter(format="$ 0.00 a")
    p.legend.location = "top_left"
    return p


def get_investment_graph(**kwargs):
    df = build_df(**kwargs)
    return build_income_graph(df)


def get_tax_graph(**kwargs):
    investment_df = build_df(**kwargs)
    contribution_df = build_distribution_df(**kwargs)
    tax_saved = investment_df[TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST].iloc[-1]
    tax_incurred_during_distributions = contribution_df[TOTAL_DISTRIBUTION_TAXES].iloc[-1]
    return build_tax_graph(tax_saved, tax_incurred_during_distributions)


def get_display_df(**kwargs):
    df = build_df(**kwargs)
    return df[
        [YEAR, ROTH_401K_BALANCE, TRADITIONAL_401K_BALANCE, TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST, TOTAL_INVESTMENT]
    ]


def get_final_results_df(**kwargs):
    df = build_df(**kwargs)
    return df[
        [
            YEAR,
            ROTH_401K_BALANCE,
            TRADITIONAL_401K_BALANCE,
            TOTAL_SAVED_TAX_INVESTED,
            TOTAL_SAVED_TAX_INVESTED_PLUS_INTEREST,
            TOTAL_INVESTMENT,
        ]
    ].tail(1)


def get_final_distributions_results_df(**kwargs):
    df = build_distribution_df(**kwargs)
    return df[
        [
            YEAR,
            TOTAL_ROTH_DISTRIBUTION,
            ROTH_401K_BALANCE,
            TOTAL_TRADITIONAL_DISTRIBUTION,
            TRADITIONAL_401K_BALANCE,
            TOTAL_DISTRIBUTION_TAXES,
        ]
    ].tail(1)


info_min_width = 350
years_slider = pn.widgets.IntSlider(
    name="Years", start=1, end=60, value=30, min_width=info_min_width, sizing_mode="stretch_width"
)
salary_input = pn.widgets.IntInput(
    name="Gross Income", value=50_000, start=0, step=1000, min_width=info_min_width, sizing_mode="stretch_width"
)
yearly_raise_input = pn.widgets.IntInput(
    name="Yearly Raise", value=3000, start=0, step=1000, min_width=info_min_width, sizing_mode="stretch_width"
)
yearly_contribution_input = pn.widgets.IntInput(
    name="Yearly 401k Contribution",
    value=23_000,
    start=0,
    step=1000,
    min_width=info_min_width,
    sizing_mode="stretch_width",
)
traditional_percent_slider = pn.widgets.IntSlider(
    name="Traditional Allocation %", start=0, end=100, value=50, min_width=info_min_width, sizing_mode="stretch_width"
)
interest_rate_input = pn.widgets.FloatInput(
    name="Investment Growth Rate %", value=7, start=0, step=0.5, min_width=info_min_width, sizing_mode="stretch_width"
)
standard_deduction_input = pn.widgets.IntInput(
    name="Standard Deduction", value=14_600, start=0, step=1000, min_width=info_min_width, sizing_mode="stretch_width"
)
inflation_input = pn.widgets.FloatInput(
    name="Inflation %", value=3, start=0, step=0.5, min_width=info_min_width, sizing_mode="stretch_width"
)
tax_brackets, tax_dependencies = build_tax_brackets(DEFAULT_TAX_BRACKETS, DEFAULT_TAX_RATES)
tax_bracket_inputs = pn.Column(*tax_brackets)
tax_brackets = pn.bind(parse_tax_brackets, tax_bracket_inputs, *tax_dependencies)

# Distribution info
distribution_years_slider = pn.widgets.IntSlider(
    name="Years", start=1, end=60, value=30, min_width=info_min_width, sizing_mode="stretch_width"
)
yearly_distributions_input = pn.widgets.IntInput(
    name="Yearly Distributions",
    value=100_000,
    start=0,
    step=1000,
    min_width=info_min_width,
    sizing_mode="stretch_width",
)
retirement_interest_rate_input = pn.widgets.FloatInput(
    name="Investment Growth Rate %", value=4, start=0, step=0.5, min_width=info_min_width, sizing_mode="stretch_width"
)


if pn.state.location:
    pn.state.location.sync(years_slider, {"value": "years"})
    pn.state.location.sync(salary_input, {"value": "salary"})
    pn.state.location.sync(yearly_raise_input, {"value": "yearly_raise"})
    pn.state.location.sync(yearly_contribution_input, {"value": "yearly_contribution"})
    pn.state.location.sync(traditional_percent_slider, {"value": "traditional_contribution"})
    pn.state.location.sync(interest_rate_input, {"value": "investment_interest_rate"})
    pn.state.location.sync(standard_deduction_input, {"value": "standard_deduction"})
    pn.state.location.sync(inflation_input, {"value": "inflation"})

    pn.state.location.sync(distribution_years_slider, {"value": "distribution_years"})
    pn.state.location.sync(yearly_distributions_input, {"value": "yearly_distributions"})
    pn.state.location.sync(retirement_interest_rate_input, {"value": "retirement_interest_rate"})

component_kwargs = {
    "years": years_slider,
    "gross_income": salary_input,
    "yearly_raise": yearly_raise_input,
    "standard_deduction": standard_deduction_input,
    "yearly_contribution": yearly_contribution_input,
    "traditional_percent": traditional_percent_slider,
    "interest_rate": interest_rate_input,
    "tax_brackets_info": tax_brackets,
    "inflation": inflation_input,
}

distribution_kwargs = {
    "distribution_years": distribution_years_slider,
    "yearly_distributions": yearly_distributions_input,
    "retirement_interest_rate": retirement_interest_rate_input,
}


template = pn.template.MaterialTemplate(
    title="401k Analyzer",
    sidebar=[
        pn.Column(
            "## Contribution Info",
            years_slider,
            salary_input,
            yearly_raise_input,
            yearly_contribution_input,
            traditional_percent_slider,
            interest_rate_input,
            "### Tax info",
            standard_deduction_input,
            "### Inflation\nInflation applies to Yearly 401k Contribution, Standard Deduction and Tax Brackets",
            inflation_input,
            "## Distribution Info",
            distribution_years_slider,
            yearly_distributions_input,
            retirement_interest_rate_input,
            pn.Accordion(("Federal Tax Brackets", tax_bracket_inputs), sizing_mode="stretch_both"),
            margin=20,
        ),
    ],
    sidebar_width=450,
)

total_investment_results = pn.pane.DataFrame(
    pn.bind(get_final_results_df, **component_kwargs), index=False, sizing_mode="stretch_both"
)
total_distribution_results = pn.pane.DataFrame(
    pn.bind(get_final_distributions_results_df, **component_kwargs, **distribution_kwargs),
    index=False,
    sizing_mode="stretch_both",
)
all_investment_results = pn.Accordion(
    (
        "All Investment Results",
        pn.pane.DataFrame(pn.bind(get_display_df, **component_kwargs), index=False, sizing_mode="stretch_width"),
    ),
    sizing_mode="stretch_both",
)
contributions_raw_data = pn.Accordion(
    (
        "Contributions Raw Data",
        pn.pane.DataFrame(pn.bind(build_df, **component_kwargs), index=False, sizing_mode="stretch_width"),
    ),
    sizing_mode="stretch_both",
)
distributions_raw_data = pn.Accordion(
    (
        "Distributions Raw Data",
        pn.pane.DataFrame(
            pn.bind(build_distribution_df, **component_kwargs, **distribution_kwargs),
            index=False,
            sizing_mode="stretch_width",
        ),
    ),
    sizing_mode="stretch_both",
)


data = pn.FlexBox(
    pn.bind(get_investment_graph, **component_kwargs),
    pn.bind(get_tax_graph, **component_kwargs, **distribution_kwargs),
    "### Total Contribution Results",
    total_investment_results,
    "### Total Distribution Results",
    total_distribution_results,
    all_investment_results,
    contributions_raw_data,
    distributions_raw_data,
    justify_content="space-evenly",
    align_content="space-evenly",
    margin=40,
)

template.main.append(data)
template.servable()
