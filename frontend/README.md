# NetlogRAG frontend

Vue 3 + Vite sučelje za lokalni FastAPI backend.

```bash
npm ci
npm run dev
```

Backend se očekuje na `http://localhost:8000`. Produkcijska provjera:

```bash
npm run lint
npm run build
npm audit --omit=dev
```

Formalni eksperimentalni rezultati ne izvode se iz UI usporedbe modela. Za njih koristi skripte u `../experiments` kako bi modeli dijelili isti zaključani testni skup.
