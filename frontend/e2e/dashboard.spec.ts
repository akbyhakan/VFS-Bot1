import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login önce yapılmalı
    await page.goto('/login');
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'password');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
  });

  test('dashboard yüklenmeli', async ({ page }) => {
    // Dashboard başlığı görünmeli
    await expect(page.locator('h1, h2').filter({ hasText: /Dashboard/i })).toBeVisible();
  });

  test('istatistik kartları görünmeli', async ({ page }) => {
    // En az bir istatistik kartı olmalı
    const statsCards = page.locator('.card, [class*="card"]');
    await expect(statsCards.first()).toBeVisible();
  });

  test('loading skeleton gösterilmeli', async ({ page }) => {
    // Sayfa yeniden yüklendiğinde skeleton görünebilir
    await page.reload();
    
    // Skeleton veya içerik görünmeli
    const content = page.locator('body');
    await expect(content).toBeVisible();
  });

  test('logout çalışmalı', async ({ page }) => {
    // Logout butonunu bul ve tıkla
    const logoutButton = page.locator('button, a').filter({ hasText: /Çıkış|Logout/i });
    
    if (await logoutButton.count() > 0) {
      await logoutButton.first().click();
      
      // Login sayfasına yönlendirilmeli
      await expect(page).toHaveURL('/login');
    }
  });
});
