import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Lightweight .env parser that avoids a dependency on `dotenv` so this
// script can be run with plain `node`.
function parseDotenv(content) {
  const lines = content.split(/\r?\n/)
  const result = {}
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const idx = trimmed.indexOf('=')
    if (idx === -1) continue
    const key = trimmed.slice(0, idx).trim()
    let val = trimmed.slice(idx + 1).trim()
    // remove surrounding quotes
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1)
    }
    result[key] = val
  }
  return result
}

// Read the upload_document/.env and write a small JS file the frontend can load
// Use fileURLToPath to handle Windows file:/// paths correctly
const __filename = fileURLToPath(import.meta.url)
// script is at upload_document/scripts/, so projectDir = one level up
const projectDir = path.resolve(path.dirname(__filename), '..')
const envPath = path.join(projectDir, '.env')

if (!fs.existsSync(envPath)) {
  console.error('.env not found at', envPath)
  process.exit(1)
}

const envContent = fs.readFileSync(envPath, { encoding: 'utf8' })
const env = parseDotenv(envContent)

// Prefer legacy SUPABASE_URL/SUPABASE_KEY, fall back to DEV/PROD
const supabaseUrl = env.SUPABASE_URL || env.SUPABASE_URL_DEV || env.SUPABASE_URL_PROD || ''
const supabaseKey = env.SUPABASE_KEY || env.SUPABASE_KEY_DEV || env.SUPABASE_KEY_PROD || ''
const apiUrl = env.API_URL || env.FRONTEND_API_URL || 'http://localhost:5000'

const out = `window.__UPLOAD_DOC_ENV = ${JSON.stringify({ SUPABASE_URL: supabaseUrl, SUPABASE_KEY: supabaseKey, API_URL: apiUrl })};\n`

const outDir = path.join(projectDir, 'frontend')
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true })
const outFile = path.join(outDir, 'env-config.js')
fs.writeFileSync(outFile, out, { encoding: 'utf8' })
console.log('Wrote frontend env config to', outFile)