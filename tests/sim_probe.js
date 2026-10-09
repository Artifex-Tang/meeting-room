const automator = require('miniprogram-automator')

async function main() {
  console.log('Connecting to ws://127.0.0.1:9420 ...')
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' })
  console.log('Connected!')

  // reLaunch directly — do NOT call currentPage() before first navigation
  console.log('Launching launch page...')
  const page = await mp.reLaunch('/pages/launch/launch')
  console.log('reLaunch done, path:', page.path)

  await page.waitFor(1000)
  const d = await page.data()
  console.log('Page data keys:', Object.keys(d))

  await mp.close()
  console.log('DONE OK')
}

main().catch(err => { console.error('ERROR:', err.message); process.exit(1) })
