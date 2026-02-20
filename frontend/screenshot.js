const puppeteer = require('puppeteer');
(async () => {
  try {
    const browser = await puppeteer.launch({ headless: "new" });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    // wait for a bit to make sure the server is up
    await new Promise(r => setTimeout(r, 5000));
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 30000 });
    // wait for UI to render
    await new Promise(r => setTimeout(r, 3000));
    await page.screenshot({ path: 'demo_screenshot.png' });
    await browser.close();
    console.log("Screenshot saved to demo_screenshot.png");
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
})();
