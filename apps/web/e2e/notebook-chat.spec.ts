import { expect, test } from '@playwright/test';

test('test_notebook_model_connection_persists_on_remount', async ({ page }) => {
  await page.goto('/notebooks');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await expect(page.getByText(/Connected:/)).toBeVisible();

  await page.goto('/notebooks/00000000-0000-0000-0000-000000000001');
  await expect(page.getByText(/Connected:/)).toBeVisible();

  await page.goto('/notebooks');
  await expect(page.getByText(/Connected:/)).toBeVisible();
});

test('model-mode-send-does-not-fall-back-to-rag', async ({ page }) => {
  await page.goto('/notebooks/00000000-0000-0000-0000-000000000001');
  await page.getByRole('combobox').selectOption('model');
  await page.getByPlaceholder('Спросите по технической документации...').fill('Привет');
  await page.getByRole('button', { name: 'Send' }).click();

  await expect(page.getByText(/Модель|Режим модели включен/)).toBeVisible();
  await expect(page.getByText(/релевантные фрагменты не найдены/)).toHaveCount(0);
});
