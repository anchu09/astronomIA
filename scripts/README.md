# scripts

- **e2e_real.py** — E2E contra la API: POST con prompt NL, comprueba success e imagen en `artifacts/test-1/image.jpg`. API tiene que estar levantada.
- **run_pipeline.py** — Pipeline en proceso (sin API): target por nombre → resolve + fetch + segment. Útil para probar sin levantar el servidor.
