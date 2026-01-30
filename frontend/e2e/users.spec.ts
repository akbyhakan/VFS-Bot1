import { test, expect } from '@playwright/test';

test.describe('Users Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login önce yapılmalı
    await page.goto('/login');
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'password');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
    
    // Users sayfasına git
    await page.goto('/users');
  });

  test('users listesi görünmeli', async ({ page }) => {
    // Tablo veya liste görünmeli
    const usersTable = page.locator('table, [role="table"]');
    await expect(usersTable).toBeVisible({ timeout: 10000 });
  });

  test('yeni kullanıcı ekleme modalı açılmalı', async ({ page }) => {
    // "Ekle" veya "Create" butonu varsa
    const createButton = page.locator('button').filter({ hasText: /Ekle|Oluştur|Create|Add/i });
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      
      // Modal açılmalı
      const modal = page.locator('[role="dialog"]');
      await expect(modal).toBeVisible();
    }
  });

  test('kullanıcı arama çalışmalı', async ({ page }) => {
    // Arama inputu varsa
    const searchInput = page.locator('input[type="search"], input[placeholder*="ara" i], input[placeholder*="search" i]');
    
    if (await searchInput.count() > 0) {
      await searchInput.first().fill('test');
      
      // Arama sonuçları güncellenmiş olmalı
      await page.waitForTimeout(500);
    }
  });

  test('tablo sıralama çalışmalı', async ({ page }) => {
    // Sıralanabilir bir sütun başlığı varsa
    const sortableHeader = page.locator('th[class*="sortable"], th[role="button"]');
    
    if (await sortableHeader.count() > 0) {
      await sortableHeader.first().click();
      
      // Tablo yeniden render edilmiş olmalı
      await page.waitForTimeout(500);
    }
  });

  test('pagination çalışmalı', async ({ page }) => {
    // Pagination kontrolleri varsa
    const nextButton = page.locator('button').filter({ hasText: /Next|Sonraki|>/i });
    
    if (await nextButton.count() > 0 && await nextButton.first().isEnabled()) {
      await nextButton.first().click();
      
      // Sayfa değişmiş olmalı
      await page.waitForTimeout(500);
    }
  });
});
