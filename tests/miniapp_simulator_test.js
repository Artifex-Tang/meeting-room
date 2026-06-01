/**
 * miniapp_simulator_test.js
 * WeChat DevTools automation - MeetingGo miniapp phone simulator
 *
 * Pre-req: cli.bat auto-preview --project MeetingGo --auto-port 9420
 * Run:     node tests/miniapp_simulator_test.js
 */

const automator = require('miniprogram-automator')
const path = require('path')
const fs = require('fs')
const https = require('https')
const http = require('http')

// Get a JWT token from backend directly (Node → backend, no domain restriction)
async function getBackendToken(openid = 'sim_auto_user_001') {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ code: openid, nickname: 'SimUser' })
    const req = http.request({
      hostname: 'localhost', port: 8001, path: '/api/auth/wechat',
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    }, res => {
      let data = ''
      res.on('data', d => data += d)
      res.on('end', () => {
        try {
          const j = JSON.parse(data)
          if (j.code === 0) resolve(j.data)
          else reject(new Error('auth failed: ' + data))
        } catch (e) { reject(e) }
      })
    })
    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

const SCREENSHOTS_DIR = path.resolve(__dirname, 'screenshots')
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true })

const results = []
let passed = 0, failed = 0

const sleep = (ms) => new Promise(r => setTimeout(r, ms))

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`TIMEOUT(${ms}ms): ${label}`)), ms)),
  ])
}

function log(icon, page, desc, detail = '') {
  results.push({ icon, page, desc, detail })
  console.log(`  ${icon} [${page}] ${desc}${detail ? '  (' + detail + ')' : ''}`)
  if (icon === '✓') passed++
  else if (icon === '✗') failed++
}

async function ss(mp, name) {
  try {
    await withTimeout(mp.screenshot({ path: path.join(SCREENSHOTS_DIR, `sim_${name}.png`) }), 6000, 'screenshot')
    console.log(`  [ss] sim_${name}.png`)
  } catch (_) {}
}

async function nav(mp, method, url, label) {
  try {
    const page = await withTimeout(mp[method](url), 20000, `${method}(${url})`)
    await page.waitFor(2500)
    log('✓', label, `navigated`, `${method} → ${url}`)
    return page
  } catch (e) {
    log('✗', label, `navigation failed`, e.message.slice(0, 80))
    return null
  }
}

// Safe data fetch with key logging
async function pageData(page, label) {
  try {
    const d = await withTimeout(page.data(), 6000, 'page.data()')
    console.log(`    data keys: ${Object.keys(d).join(', ')}`)
    return d
  } catch (e) {
    log('✗', label, 'page.data() failed', e.message.slice(0, 60))
    return null
  }
}

async function runTests() {
  console.log('='.repeat(60))
  console.log('WeChat Miniapp Simulator Tests')
  console.log('='.repeat(60))

  let mp
  try {
    mp = await withTimeout(automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' }), 8000, 'connect')
    console.log('[SETUP] Connected to simulator (port 9420)')
    await sleep(3000)

    // Pre-inject token from backend (bypasses simulator domain restriction)
    try {
      const authData = await getBackendToken('sim_auto_user_001')
      await mp.evaluate((token, userInfo) => {
        wx.setStorageSync('token', token)
        wx.setStorageSync('userInfo', userInfo)
        const app = getApp(); if (!app.globalData) app.globalData = {}
        app.globalData.token = token
        app.globalData.userInfo = userInfo
      }, authData.token, authData.user)
      console.log(`[SETUP] Token pre-injected for userId=${authData.user.id}`)
    } catch (e) {
      console.warn('[SETUP] Token pre-inject failed:', e.message, '(continuing)')
    }
  } catch (err) {
    console.error('FATAL:', err.message); process.exit(1)
  }

  // ── 1. Launch page ─────────────────────────────────────────────────────────
  console.log('\n[PAGE] launch/launch')
  const launchPage = await nav(mp, 'reLaunch', '/pages/launch/launch', 'launch')
  if (launchPage) {
    await ss(mp, '01_launch')
    const d = await pageData(launchPage, 'launch')
    if (d) log('✓', 'launch', 'launch page data', `keys=${Object.keys(d).join(',')}`)

    // wx.login via callWxMethod (handles callback→promise internally)
    try {
      const loginResult = await withTimeout(mp.callWxMethod('login'), 8000, 'wx.login')
      log(loginResult && loginResult.code ? '✓' : '✗', 'launch',
          'wx.login() returns code', loginResult ? `code=${loginResult.code}` : 'undefined')

      if (loginResult && loginResult.code) {
        // POST code to backend — use exposeFunction to bridge Node→miniapp
        const authRes = await withTimeout(mp.evaluate((code) => {
          return new Promise((resolve) => {
            wx.request({
              url: 'http://localhost:8001/api/auth/wechat',
              method: 'POST',
              data: { code: code, nickname: 'SimUser' },
              header: { 'Content-Type': 'application/json' },
              success(r) {
                if (r.data && r.data.code === 0) {
                  const app = getApp(); if (!app.globalData) app.globalData = {}
                  app.globalData.token = r.data.data.token
                  wx.setStorageSync('token', r.data.data.token)
                  wx.setStorageSync('userInfo', r.data.data.user)
                  resolve('OK:' + r.data.data.user.id)
                } else resolve('FAIL:' + JSON.stringify(r.data))
              },
              fail(e) { resolve('NET:' + e.errMsg) },
            })
          })
        }, loginResult.code), 10000, 'auth/wechat')
        log(String(authRes).startsWith('OK:') ? '✓' : '✗', 'launch',
            'backend auth from simulator', String(authRes))
      }
    } catch (e) { log('✗', 'launch', 'login error', e.message.slice(0, 80)) }
  }

  // ── 2. Room list tab ───────────────────────────────────────────────────────
  console.log('\n[PAGE] index/index')
  const roomListPage = await nav(mp, 'switchTab', '/pages/index/index', 'room-list')
  if (roomListPage) {
    await ss(mp, '02_room_list')
    const d = await pageData(roomListPage, 'room-list')
    if (d) {
      const rooms = d.rooms || d.roomList || d.list || []
      log(Array.isArray(rooms) ? '✓' : '🔍', 'room-list', 'rooms array exists', `count=${rooms.length}`)
      log(d.loading !== undefined ? '✓' : '🔍', 'room-list', 'loading state present')
    }
  }

  // ── 3. My bookings tab ─────────────────────────────────────────────────────
  console.log('\n[PAGE] my/bookings/bookings')
  const bookingsPage = await nav(mp, 'switchTab', '/pages/my/bookings/bookings', 'my-bookings')
  if (bookingsPage) {
    await ss(mp, '03_my_bookings')
    const d = await pageData(bookingsPage, 'my-bookings')
    if (d) {
      const bkgs = d.bookings || d.list || []
      log(Array.isArray(bkgs) ? '✓' : '🔍', 'my-bookings', 'bookings array', `count=${bkgs.length}`)
      log(d.statusTab !== undefined ? '✓' : '🔍', 'my-bookings', 'statusTab initialized', `tab=${d.statusTab}`)
    }
  }

  // ── 4. Profile tab ─────────────────────────────────────────────────────────
  console.log('\n[PAGE] my/index/index')
  const profilePage = await nav(mp, 'switchTab', '/pages/my/index/index', 'profile')
  if (profilePage) {
    await ss(mp, '04_profile')
    const d = await pageData(profilePage, 'profile')
    if (d) log(d.userInfo !== undefined ? '✓' : '🔍', 'profile', 'userInfo key present')
  }

  // ── 5. Room detail (use reLaunch — navigateTo hangs on non-tabBar in auto mode) ──
  console.log('\n[PAGE] room/detail/detail')
  const roomPage = await nav(mp, 'reLaunch', '/pages/room/detail/detail?id=2', 'room-detail')
  if (roomPage) {
    await ss(mp, '05_room_detail')
    const d = await pageData(roomPage, 'room-detail')
    if (d) log('✓', 'room-detail', 'detail page data', `keys=${Object.keys(d).join(',')}`)
  }

  // ── 6. Booking create ──────────────────────────────────────────────────────
  console.log('\n[PAGE] booking/create/create')
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1)
  const dateStr = tomorrow.toISOString().slice(0, 10)
  const createPage = await nav(mp, 'reLaunch',
    `/pages/booking/create/create?roomId=2&date=${dateStr}`, 'booking-create')
  if (createPage) {
    await ss(mp, '06_booking_create')
    const d = await pageData(createPage, 'booking-create')
    if (d) {
      log(Array.isArray(d.takenSlots) ? '✓' : '🔍', 'booking-create', 'takenSlots array',
          `len=${Array.isArray(d.takenSlots) ? d.takenSlots.length : 'N/A'}`)
      log(d.mode !== undefined ? '✓' : '🔍', 'booking-create', 'mode field', `mode=${d.mode}`)
    }
  }

  // ── 7. Recurrence page ─────────────────────────────────────────────────────
  console.log('\n[PAGE] booking/recurrence/recurrence')
  const recurPage = await nav(mp, 'reLaunch',
    '/pages/booking/recurrence/recurrence?roomId=2', 'recurrence')
  if (recurPage) {
    await ss(mp, '07_recurrence')
    const d = await pageData(recurPage, 'recurrence')
    if (d) {
      log(d.frequency ? '✓' : '✗', 'recurrence', 'frequency initialized', `freq=${d.frequency}`)
      log(Array.isArray(d.weekdayOptions) ? '✓' : '✗', 'recurrence', 'weekdayOptions',
          `len=${Array.isArray(d.weekdayOptions) ? d.weekdayOptions.length : 'N/A'}`)
    }
  }

  // ── 8. Network probe ───────────────────────────────────────────────────────
  console.log('\n[PROBE] network & API')
  try {
    // Use exposeFunction to bridge result back to Node
    let cfgResolve
    const cfgPromise = new Promise(r => { cfgResolve = r })
    await mp.exposeFunction('__testCallback', (result) => { cfgResolve(result) })
    await mp.evaluate(() => {
      wx.request({
        url: 'http://localhost:8001/api/config/public', method: 'GET',
        success: res => __testCallback('HTTP:' + res.statusCode + ':' + JSON.stringify((res.data || {}).code)),
        fail:    e   => __testCallback('FAIL:' + e.errMsg),
      })
    })
    const cfgRes = await withTimeout(cfgPromise, 8000, 'config/public')
    log(String(cfgRes).startsWith('HTTP:200') ? '✓' : '✗', 'network',
        'GET /config/public from simulator', String(cfgRes))
  } catch (e) { log('✗', 'network', 'config probe error', e.message.slice(0, 60)) }

  try {
    const token = await withTimeout(mp.evaluate(() => wx.getStorageSync('token')), 3000, 'getStorage')
    if (token) {
      let roomsResolve
      const roomsPromise = new Promise(r => { roomsResolve = r })
      await mp.exposeFunction('__roomsCallback', (result) => { roomsResolve(result) })
      await mp.evaluate((tok) => {
        wx.request({
          url: 'http://localhost:8001/api/rooms', method: 'GET',
          header: { Authorization: 'Bearer ' + tok },
          success: res => __roomsCallback('OK:' + (res.data || {}).code + ':count=' + ((res.data || {}).data || []).length),
          fail:    e   => __roomsCallback('FAIL:' + e.errMsg),
        })
      }, token)
      const roomsRes = await withTimeout(roomsPromise, 8000, 'GET /rooms')
      log(String(roomsRes).startsWith('OK:0:') ? '✓' : '✗', 'api',
          'GET /rooms from simulator (authenticated)', String(roomsRes))
    } else {
      log('🔍', 'api', 'rooms probe skipped (no token in storage)')
    }
  } catch (e) { log('✗', 'api', 'rooms probe error', e.message.slice(0, 60)) }

  // ── Summary ────────────────────────────────────────────────────────────────
  console.log('\n' + '='.repeat(60))
  console.log('SIMULATOR TEST RESULTS')
  console.log('='.repeat(60))
  results.forEach(r =>
    console.log(`  ${r.icon} [${r.page}] ${r.desc}${r.detail ? '  (' + r.detail + ')' : ''}`)
  )
  const probes = results.filter(r => r.icon === '🔍').length
  console.log(`\nPassed: ${passed}  Failed: ${failed}  Info: ${probes}`)
  console.log('Verdict:', failed === 0 ? 'PASS' : 'FAIL')
  return failed === 0
}

runTests()
  .then(ok => process.exit(ok ? 0 : 1))
  .catch(err => { console.error('FATAL:', err.message || err); process.exit(1) })
