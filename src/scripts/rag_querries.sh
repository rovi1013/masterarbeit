#!/usr/bin/env bash
set -e

QUESTIONS=(
  # Allgemeine Faktenfragen - 8
  "What is the main objective of the European Green Deal?"
  "According to the World Energy Outlook 2025, which energy source shows the fastest growth in electricity generation?"
  "What role does renewable electricity play in global decarbonisation according to the IEA?"
  "Which sectors are identified as the largest contributors to global energy demand growth?"
  "What is the projected share of renewables in global electricity generation by 2030?"
  "What does the World Energy Outlook say about the future role of coal in the global energy mix?"
  "Which regions are expected to drive most of the future growth in electricity demand?"
  "What are the main policy goals of the European Green Deal related to climate neutrality?"
  # Konkrete Zahlen und Tabellen - 7
  "How many gigawatts of renewable capacity are projected to be added globally by 2030?"
  "What is the estimated percentage increase in global electricity demand caused by data centres and AI?"
  "According to the reports, how many people worldwide still lack access to electricity?"
  "What share of global CO₂ emissions is attributed to the energy sector?"
  "How much investment per year is projected for electricity grids globally?"
  "What is the projected global temperature increase under current policies by 2100?"
  "How large is the projected global LNG supply overcapacity around 2030?"
  # Vergleichsfragen - 5
  "How do the European Green Deal and the World Energy Outlook differ in their approach to achieving climate neutrality?"
  "Compare the role of renewables in advanced economies versus emerging economies."
  "How does the outlook for renewable energy differ between the Current Policies Scenario and the Net Zero Scenario?"
  "What similarities exist between the European Green Deal and IEA recommendations regarding renewable expansion?"
  "How do energy security concerns influence renewable energy policies according to the reports?"
  # Kontext Fragen, 'selber denken nötig' - 5
  "Why is grid infrastructure considered a bottleneck for renewable energy expansion?"
  "What challenges do high shares of wind and solar pose for electricity systems?"
  "Why does renewable growth not automatically lead to declining global emissions?"
  "How does electrification affect overall energy efficiency?"
  "What role do critical minerals play in the energy transition?"
  # Fragen mit möglichst langen Antworten - 5
  "Explain how renewable energy expansion affects energy security."
  "Describe the relationship between electricity demand growth and digitalisation."
  "Explain why achieving net zero emissions requires more than renewable deployment."
  "Summarise the main risks to global energy systems identified in the World Energy Outlook."
  "Describe how policy uncertainty affects long-term energy investments."
  # Fragen die aus dem Kontext heraus nicht beantwortet werden können - 5
  "What percentage of Germany’s electricity demand in 2035 will be met exclusively by offshore wind?"
  "How much energy does the European Green Deal project will be saved specifically by AI optimisation?"
  "What is the exact carbon footprint of large language models according to the IEA?"
  "Which single renewable technology will completely replace fossil fuels by 2040?"
  "What is the precise energy consumption of ChatGPT mentioned in the World Energy Outlook?"
)

for q in "${QUESTIONS[@]}"; do
  curl -s -X POST http://127.0.0.1:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}"
done
