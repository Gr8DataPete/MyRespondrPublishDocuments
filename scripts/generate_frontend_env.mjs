import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import dotenv from 'dotenv'

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

const env = dotenv.parse(fs.readFileSync(envPath))

// Prefer legacy SUPABASE_URL/SUPABASE_KEY, fall back to DEV
const supabaseUrl = env.SUPABASE_URL || env.SUPABASE_URL_DEV || env.SUPABASE_URL_PROD || ''
const supabaseKey = env.SUPABASE_KEY || env.SUPABASE_KEY_DEV || env.SUPABASE_KEY_PROD || ''

const out = `window.__UPLOAD_DOC_ENV = ${JSON.stringify({ SUPABASE_URL: supabaseUrl, SUPABASE_KEY: supabaseKey })};\n`

const outDir = path.join(projectDir, 'frontend')
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true })
const outFile = path.join(outDir, 'env-config.js')
fs.writeFileSync(outFile, out, { encoding: 'utf8' })
console.log('Wrote frontend env config to', outFile)