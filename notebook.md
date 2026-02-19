# Notebook QA Notes

### Известные ограничения окружения разработки
E2E-тесты Notebook требуют локальной установки браузеров:

```bash
cd apps/web && npx playwright install --with-deps chromium
npm run test:e2e:notebook
```

В tool-окружении и некоторых CI они пропускаются из-за сетевых политик.
