# NHS Antidepressant Prescribing Analysis: Trends in Volume, Cost, and Regional Dynamics (2021-2025)

## Executive Summary

This project presents a comprehensive analysis of antidepressant prescription trends within the National Health Service (NHS) in England from January 2021 to March 2025. The core objective was to investigate the dynamics of prescription volume (items) and associated costs at national, regional, and specific drug levels.

The analysis reveals a significant divergence: while the total number of antidepressant items prescribed consistently increased across all NHS regions, total national prescribing costs experienced a dramatic reduction between 2021 and 2022, subsequently stabilizing at a lower baseline. This cost containment was predominantly driven by the widespread genericisation of high-volume drugs, notably Sertraline hydrochloride. Despite accounting for over a quarter of all antidepressant items nationally, Sertraline's contribution to total cost is proportionally lower, reflecting a significantly reduced unit cost (overall mean cost per item: £2.37). Regional analysis further highlighted variations in Sertraline's mean cost per item, with the South East recording the highest (£2.74) and North East and Yorkshire the lowest (£2.14). This project underscores the NHS's success in managing pharmaceutical expenditure for antidepressants while effectively meeting growing patient demand.

## 1\. Problem Statement & Motivation

Antidepressants are a critical component of mental healthcare provision and represent a substantial portion of pharmaceutical expenditure within the NHS. Understanding the evolving patterns of their prescription volume and cost is vital for informed decision-making, effective resource allocation, and ensuring the long-term sustainability of mental health services in England. This project seeks to provide data-driven insights into these trends, addressing questions such as:

  * How have national antidepressant prescribing volumes and costs changed over time?
  * What are the key drivers behind these changes, particularly regarding specific drugs?
  * Are there significant regional variations in antidepressant prescribing volume and cost?
  * What are the implications of these trends for NHS budgeting and mental health policy?

## 2\. Data Sources

The data for this analysis was sourced from the NHS Business Services Authority (NHS BSA), which publishes detailed prescription data. The raw data was obtained using a Python web scraping script.

**Data Grouping:**
The dataset was structured to provide granular insights, grouped by:

  * NHS Region (`REGION_NAME`)
  * Year (`YEAR`)
  * Year-Month (`YEAR_MONTH`)
  * BNF Chemical Substance (`BNF_CHEMICAL_SUBSTANCE`)
  * Number of Items (`ITEMS`)
  * Cost (`COST`)

## 3\. Methodology

This project employs a multi-faceted analytical approach to explore antidepressant prescription trends:

1.  **Data Acquisition:** A custom Python script (`nhs_scraper.py`) was developed to scrape the relevant prescription data from the NHS BSA website.
2.  **Data Preprocessing & Grouping:** The raw data was cleaned, transformed, and aggregated within a Jupyter Notebook to create a structured dataset suitable for analysis.
3.  **National Trend Analysis:**
      * Time-series analysis of national monthly prescribing costs to identify overall patterns and anomalies.
      * Annual aggregation of national total items and total costs to observe macro-level shifts.
      * Statistical distribution analysis of monthly costs to understand variability over time.
4.  **Drug-Specific Analysis:**
      * Identification of top antidepressant drugs by both total items and total cost.
      * Comparative analysis of monthly item and cost trends for these top drugs to determine individual drivers.
      * Calculation of overall percentage contributions for each drug to total items and total cost to assess relative cost-efficiency.
      * **In-depth Analysis of Sertraline hydrochloride:** Focused examination of its contribution percentages, overall mean cost per item (£2.37), and regional variations in its mean cost per item and total spending.
5.  **Regional Analysis:**
      * Annual total items and costs were broken down by individual NHS regions to identify geographical disparities in prescribing volume and expenditure.
6.  **Visualization:** Various plots (line charts, bar charts) and tables were generated to visually represent trends and insights.
7.  **Interpretation:** Findings were interpreted in the context of known healthcare policies, market dynamics (e.g., genericisation), and public health trends.

The analysis period spans from January 2021 to March 2025. It is important to note that data for 2025 represents a partial year (Q1 only).

## 4\. Key Findings & Insights

### 4.1 Divergent Trends: Items Increasing, Costs Decreasing/Stabilizing

  * **Rising Prescription Volume:** The total number of antidepressant items prescribed nationally consistently increased from approximately 83 million in 2021 to over 90 million in 2024. This upward trend was observed across all NHS regions.
  * **Significant Cost Reduction & Stabilization:** National monthly prescribing costs saw a dramatic decline from early 2021, settling at a new, lower baseline from 2022 onwards. The annual mean monthly cost dropped sharply from around £24.5 million in 2021 to approximately £19.0 million in 2022, maintaining this level through 2024. The distribution of monthly costs also showed reduced variability from 2022.

### 4.2 The Pivotal Role of Sertraline Hydrochloride

  * **Dominance in Volume, Efficiency in Cost:** Sertraline hydrochloride consistently remained the most prescribed antidepressant throughout the period, with monthly item counts often exceeding 2 million. Despite this high volume, its total cost plummeted significantly in 2021. Sertraline accounts for 25.67% of all antidepressant items but only 21.99% of the total cost across the entire period, indicating its cost-efficiency on a per-item basis.
  * **Genericisation Impact:** The sharp reduction in Sertraline's unit cost, leading to its disproportionately lower cost contribution relative to its item volume, strongly points to the widespread impact of patent expiry and the availability of cheaper generic versions. This was the primary driver for the overall national cost reduction.
  * **Regional Cost Variations for Sertraline:** The overall mean cost per item for Sertraline was £2.37. However, regional analysis shows variation: the South East had the highest mean cost per item for Sertraline at £2.74, while North East and Yorkshire had the lowest at £2.14. North East and Yorkshire also recorded the highest total spending on Sertraline, whereas the South West had the lowest.

### 4.3 Other Key Drug Dynamics

  * **High Unit-Cost Drugs:** While Sertraline drove down overall costs, drugs like Venlafaxine present a different dynamic. Venlafaxine ranked 6th in terms of total items (6.44%) but jumped to 2nd in terms of total cost (16.52%). This signifies a considerably higher average cost per item. Other drugs such as Duloxetine hydrochloride and Trazodone hydrochloride also showed a higher cost percentage relative to their item percentage. Notably, some drugs like Vortioxetine, Trimipramine maleate, and Tranylcypromine sulfate appeared in the top 10 by cost but not by items, indicating very high per-item costs.
  * **Cost-Efficient Generics:** Alongside Sertraline, older generics like Amitriptyline hydrochloride and Citalopram hydrobromide consistently provided a larger share of prescriptions for a proportionally smaller share of the overall cost, demonstrating their cost-efficiency.

### 4.4 Regional Prescribing Patterns

  * All NHS regions experienced an increase in antidepressant prescribing items from 2021 to 2024.
  * North East and Yorkshire (17.1%) and London (15.1%) showed the highest percentage increases in items.
  * Midlands and North East and Yorkshire consistently had the highest annual prescribing volumes in absolute terms.
  * All regions also saw substantial cost reductions between 2021 and 2024, ranging from -18.8% to -24.4%. This consistent reduction across regions reinforces the pervasive impact of national factors like generic drug availability.

### 4.5 Seasonal Variation in Costs

  * No strong, consistent, annually repeating seasonal pattern was clearly evident in the overall national prescribing costs.
  * Monthly cost fluctuations, including a notable spike in May/June 2024, did not consistently align with typical seasonal patterns of increased antidepressant *prescribing volume* (often seen in autumn/winter). This suggests that factors like drug price fluctuations or procurement cycles may play a more significant role in cost variations than pure seasonal demand shifts.

## 5\. Implications & Recommendations

1.  **Reinforce Generic Prescribing Policies:** The success demonstrated by Sertraline hydrochloride clearly highlights the immense cost-saving potential of genericisation. The NHS should continue to prioritize and promote generic prescribing for all eligible drugs to sustain financial efficiency.
2.  **Strategic Procurement for High-Cost Drugs:** While high-volume generics are well-managed, a nuanced approach is needed for drugs like Venlafaxine, Duloxetine, and particularly the very high-cost, low-volume drugs (e.g., Vortioxetine). The NHS should scrutinize their cost-effectiveness, investigate reasons for high unit prices, and explore opportunities for more favorable pricing agreements or alternative treatment pathways where clinically appropriate.
3.  **Address Regional Disparities in Unit Costs:** The variations in Sertraline's mean cost per item across regions (e.g., South East vs. North East and Yorkshire) suggest opportunities for best practice sharing in procurement and prescribing within the NHS. Further investigation into the factors driving these regional differences could yield additional efficiencies.
4.  **Resource Planning for Growing Demand:** The continuous increase in antidepressant item volume across all regions signifies a growing demand for mental health support via pharmacotherapy. The NHS must proactively plan and allocate resources for primary care services, pharmacy dispensing, and wider mental health support to meet this rising demand sustainably.
5.  **Continuous Monitoring and Vigilance:** While costs have largely stabilized, the NHS should maintain robust monitoring of drug prices and supply chains to quickly identify and respond to any inflationary pressures or supply disruptions that could impact expenditure.

## 6\. Technologies Used

  * Python
  * Pandas (for data manipulation and analysis)
  * Matplotlib (for plotting and visualization)
  * Seaborn (for enhanced visualizations)
  * Jupyter Notebook (for interactive analysis and presentation)
  * VSCode

## 7\. Project Structure

```
NHS_Antidepressant_Prescription_Analysis/
├── README.md                          (This file)
├── requirements.txt                   (Python dependencies)
├── pca_data/
│   ├── combined_pca_data
├── Antidepressant_Analysis.ipynb  (Jupyter Notebook with detailed analysis, plots, and interpretations)
│   
├── scraper.py (Python script for web scraping NHS data)
│                    
├── NHS_Antidepressant_Prescription_Report.pdf (The final, detailed project report)
                         
```

## 8\. How to Run/Reproduce

To reproduce this analysis:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/NHS_Antidepressant_Prescription_Analysis.git
    cd NHS_Antidepressant_Prescription_Analysis
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the scraper:**
    If you wish to obtain the latest data or verify the scraping process, execute:
    ```bash
    python scripts/nhs_scraper.py
    ```
    *(Note: This scraper is designed for the NHS BSA website structure at the time of development and may require updates if the website changes.)*
5.  **Open and run the Jupyter Notebook:**
    ```bash
    jupyter notebook notebooks/Antidepressant_Analysis.ipynb
    ```
    Execute the cells sequentially within the notebook to see the data loading, processing, analysis, and visualizations.

## 9\. Future Work

  * **Patient Demographics:** Integrate patient demographic data (age, gender, deprivation index) to understand correlations with prescribing patterns.
  * **Clinical Outcomes:** Explore the link between prescribing trends and clinical outcomes or mental health service utilization.
  * **Specific Formulations/Strengths:** Delve deeper into specific drug formulations or strengths to understand their impact on cost and prescribing choices.
  * **Impact of Policy Changes:** Analyze the direct impact of specific NHS mental health policies or guideline updates on prescribing trends.
  * **Forecast antidepressant demand using time series models**

## 10\. Contact

  * **[Ezekwem Desmond/https://ezekwemdesmond.com/]**
  * **[engrstephdez@gmail.com]**
