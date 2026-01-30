import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('başarılı giriş yapabilmeli', async ({ page }) => {
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'password');
    await page.click('button[type="submit"]');
    
    // Dashboard'a yönlendirilmeli
    await expect(page).toHaveURL('/');
  });

  test('hatalı giriş hata mesajı göstermeli', async ({ page }) => {
    await page.fill('[name="username"]', 'wrong');
    await page.fill('[name="password"]', 'wrong');
    await page.click('button[type="submit"]');
    
    // Hata mesajı görünmeli (sonner toast kullanıldığı için)
    await expect(page.locator('[data-sonner-toast]')).toBeVisible();
  });

  test('boş form submit edilememeli', async ({ page }) => {
    await page.click('button[type="submit"]');
    
    // Hata mesajları görünmeli
    await expect(page.locator('text=/Kullanıcı adı gerekli/i')).toBeVisible();
  });

  test('rate limiting çalışmalı', async ({ page }) => {
    // 5 başarısız deneme yap
    for (let i = 0; i < 5; i++) {
      await page.fill('[name="username"]', 'wrong');
      await page.fill('[name="password"]', 'wrong');
      await page.click('button[type="submit"]');
      await page.waitForTimeout(500);
    }

    // Submit butonu disabled olmalı
    const submitButton = page.locator('button[type="submit"]');
    await expect(submitButton).toBeDisabled();
    
    // "Bekleyin" mesajı görünmeli
    await expect(submitButton).toContainText(/Bekleyin/i);
  });

  test('remember me checkbox çalışmalı', async ({ page }) => {
    const rememberCheckbox = page.locator('input[type="checkbox"]#rememberMe');
    
    // Checkbox'ı işaretle
    await rememberCheckbox.check();
    await expect(rememberCheckbox).toBeChecked();
    
    // İşareti kaldır
    await rememberCheckbox.uncheck();
    await expect(rememberCheckbox).not.toBeChecked();
  });
});
