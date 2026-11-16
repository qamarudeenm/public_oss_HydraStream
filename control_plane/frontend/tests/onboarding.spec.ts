/**
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { test, expect } from '@playwright/test';

test.describe('Onboarding Flow', () => {
  test('should allow a user to create a new tenant through the wizard', async ({ page }) => {
    console.log('Navigating to home page...');
    await page.goto('/', { waitUntil: 'networkidle' });
    console.log('Home page reached. Waiting for "Create Tenant" button...');
    
    // 2. Click "Create Tenant"
    const createButton = page.getByRole('link', { name: 'Create Tenant' });
    await expect(createButton).toBeVisible({ timeout: 60000 });
    console.log('Clicking "Create Tenant"...');
    await createButton.click();
    await expect(page).toHaveURL('/tenants/new', { timeout: 30000 });
    await expect(page.getByText('Create New Tenant')).toBeVisible();

    // 3. Step 1: General Configuration
    console.log('Filling in Step 1...');
    const tenantId = 'test-tenant-' + Math.random().toString(36).substring(7);
    await page.fill('#id', tenantId);
    await page.fill('#name', 'Test Tenant Corp');
    await page.selectOption('#flink_version', '1.19.1');
    await page.selectOption('#dbt_version', '1.7.0');
    await page.click('button:has-text("Next Step")');
    await page.waitForTimeout(1000); // Allow step transition

    // 4. Step 2: Kafka Source Settings
    console.log('Filling in Step 2...');
    await expect(page.getByText('Kafka Source Settings')).toBeVisible({ timeout: 30000 });
    await page.fill('input[id="kafka.bootstrap_servers"]', 'localhost:9092');
    await page.fill('input[id="kafka.topic"]', 'test-topic');
    await page.fill('input[id="kafka.group_id"]', 'test-group');
    await page.click('button:has-text("Next Step")');
    await page.waitForTimeout(1000); // Allow step transition

    // 5. Step 3: Destination (JDBC Sink) Settings
    console.log('Filling in Step 3...');
    await expect(page.getByText('Destination (JDBC Sink) Settings')).toBeVisible({ timeout: 30000 });
    
    // Fill each field carefully
    const fields = [
      { id: 'sink.jdbc_url', val: 'jdbc:mysql://localhost:9004/test_db' },
      { id: 'sink.user', val: 'test_user' },
      { id: 'sink.password', val: 'test_pass' },
      { id: 'sink.summary_table', val: 'test_summary' },
      { id: 'sink.metrics_table', val: 'test_metrics' },
    ];
    
    for (const field of fields) {
      const locator = page.locator(`input[id="${field.id}"]`);
      await locator.waitFor({ state: 'visible', timeout: 30000 });
      await locator.fill(field.val);
      await page.waitForTimeout(200); // Small pause after fill
    }

    await page.click('button:has-text("Next Step")');
    await expect(page.getByText('Environment Runtime Mapping')).toBeVisible({ timeout: 30000 });
    await page.fill('input[id="environments.dev.dbt_service_token"]', 'dev-token');
    await page.fill('input[id="environments.staging.dbt_service_token"]', 'staging-token');
    await page.fill('input[id="environments.prod.dbt_service_token"]', 'prod-token');

    // 6. Submit: Deploy Pipeline
    console.log('Submitting form...');
    await page.click('button:has-text("Deploy Pipeline")');

    // 7. Verify redirection back to dashboard
    console.log('Waiting for redirection...');
    await expect(page).toHaveURL('/', { timeout: 60000 });
    
    // 8. Verify the new tenant appears in the table
    console.log('Verifying tenant in table...');
    await expect(page.getByText('Test Tenant Corp')).toBeVisible({ timeout: 30000 });
    console.log('Test completed successfully!');
  });
});
