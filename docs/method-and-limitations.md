# Method and limitations

## Inputs
The scoring service evaluates soil type, soil pH, nitrogen, phosphorus, potassium, rainfall, temperature, humidity and season. pH, rainfall, temperature, humidity, soil type and season are required; N/P/K are optional and influence completeness.

## Scoring
Each crop profile contains ideal and tolerable ranges for seven numeric measurements, supported soil types and seasons. The scoring service evaluates each factor and returns ranked suitability scores, factor breakdowns, strengths, weaknesses and confidence/completeness metadata. The ranking is comparative within the active crop dataset.

## Explanations
Gemini explanations are optional and server-side. If Gemini is unavailable or fails within its configured timeout, a rules-based fallback explanation is returned. The response labels the explanation source.

## Limitations
The initial crop profiles are educational estimates, not a validated agronomic database. The model does not estimate yield, profit, pest pressure, irrigation availability, market demand, local regulations or future weather. Input measurement quality and dataset coverage affect ranking quality. A high score is not a probability of success.

## Advisory disclaimer
Use results to explore options and prepare questions, not as standalone planting instructions. Validate with a current soil test and qualified local agronomic advice for the relevant region and season.
