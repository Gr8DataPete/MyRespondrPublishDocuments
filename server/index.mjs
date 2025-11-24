import express from 'express'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createClient } from '@supabase/supabase-js'
import multer from 'multer'
import { v4 as uuidv4 } from 'uuid'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const app = express()

app.use(express.json())

// Simple request logger to help debugging frontend requests
app.use((req, res, next) => {
  console.log(`[upload_document] Incoming request: ${req.method} ${req.url}`)
  next()
})

// Prepare multer for parsing multipart/form-data (file uploads) into memory
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: Number(process.env.MAX_FILE_SIZE_BYTES || 50 * 1024 * 1024) } })

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.SUPABASE_URL_DEV || ''
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.SUPABASE_KEY_DEV || ''

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.warn('Warning: SUPABASE_URL or SUPABASE_KEY not set in environment. Server signin will fail.')
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Optional: separate Supabase project for storage uploads
const SUPABASE_UPLOAD_URL = process.env.SUPABASE_UPLOAD_URL || ''
const SUPABASE_UPLOAD_KEY = process.env.SUPABASE_UPLOAD_KEY || ''

let storageClient = supabase
if (SUPABASE_UPLOAD_URL && SUPABASE_UPLOAD_KEY) {
  console.log('[upload_document] Using separate Supabase client for storage uploads')
  storageClient = createClient(SUPABASE_UPLOAD_URL, SUPABASE_UPLOAD_KEY)
} else {
  console.log('[upload_document] Using primary Supabase client for storage uploads')
}

app.post('/api/signin', async (req, res) => {
  try {
    const { email, password } = req.body || {}
    if (!email || !password) return res.status(400).json({ error: 'email and password required' })

    console.log(`[upload_document] Sign-in attempt for email=${email} password_length=${String(password?.length)}`)

    const { data: signInData, error: signInError } = await supabase.auth.signInWithPassword({ email, password })
    if (signInError) {
      console.error('[upload_document] Sign-in error:', signInError)
      return res.status(401).json({ error: signInError.message || String(signInError) })
    }

    const user = signInData.user
    console.log('[upload_document] Signed in user id=', user?.id, 'email=', user?.email)

    let orgId = user?.user_metadata?.org_id || null
    if (!orgId) {
      console.log('[upload_document] org_id not in metadata; querying UserProfiles table...')
      const { data: profile, error: profileErr } = await supabase.from('UserProfiles').select('org_id').eq('id', user.id).limit(1).maybeSingle()
      if (profileErr) {
        console.error('[upload_document] Error querying UserProfiles:', profileErr)
      } else if (profile && profile.org_id) {
        orgId = profile.org_id
        console.log('[upload_document] Found org_id in UserProfiles:', orgId)
      }
    } else {
      console.log('[upload_document] org_id from metadata:', orgId)
    }

    return res.json({ success: true, user: { id: user.id, email: user.email }, org_id: orgId })
  } catch (err) {
    console.error('[upload_document] Unexpected error in /api/signin:', err)
    return res.status(500).json({ error: String(err) })
  }
})


// Upload document endpoint (receives multipart/form-data with `file`, optional `user_id`, `org_id`, `description`)
app.post('/api/organizations/me/documents', upload.single('file'), async (req, res) => {
  try {
    console.log('[upload_document] POST /api/organizations/me/documents - handler')

    const file = req.file
    if (!file) return res.status(400).json({ error: 'file is required' })

    // Accept user_id/org_id from form fields (frontend should set these after sign-in)
    const userId = (req.body && req.body.user_id) || null
    const orgId = (req.body && req.body.org_id) || null
    const description = (req.body && req.body.description) || null

    console.log('[upload_document] Received upload', { originalName: file.originalname, size: file.size })
    console.log('[upload_document] Received form fields:', req.body)

    if (!SUPABASE_URL || !SUPABASE_KEY) {
      console.warn('[upload_document] SUPABASE_URL/SUPABASE_KEY not set; cannot upload')
      return res.status(500).json({ error: 'server not configured for uploads' })
    }

    const bucket = process.env.SUPABASE_UPLOAD_BUCKET || process.env.SUPABASE_BUCKET || 'organization-documents'
    const docId = uuidv4()
    // construct a storage path like orgs/{orgId}/{uuid}_{originalName}
    const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_')
    const storagePath = orgId ? `orgs/${orgId}/${docId}_${safeName}` : `uploads/${docId}_${safeName}`

    // Upload to Supabase storage
    const { data: uploadData, error: uploadError } = await storageClient.storage.from(bucket).upload(storagePath, file.buffer, {
      contentType: file.mimetype,
      upsert: false
    })

    if (uploadError) {
      console.error('[upload_document] Supabase storage upload error:', uploadError)
      return res.status(500).json({ error: uploadError.message || String(uploadError) })
    }

    // Persist metadata to a table (user must create this table in Supabase)
    const now = new Date().toISOString()
    const documentRow = {
      document_id: docId,
      user_id: userId,
      org_id: orgId,
      filename: file.originalname,
      storage_path: storagePath,
      bucket: bucket,
      content_type: file.mimetype,
      size_bytes: file.size,
      description: description,
      uploaded_at: now
    }

    // Persist metadata into the Organization_Documents table (renamed from Document_manager)
    const { data: insertData, error: insertError } = await storageClient.from('Organization_Documents').insert([documentRow])
    if (insertError) {
      console.error('[upload_document] Error inserting document metadata:', insertError)
      // If the table does not exist, give a friendly hint to run the SQL included in the repo
      const msg = insertError && insertError.message && insertError.message.includes('Could not find the table')
        ? 'Database table Organization_Documents not found in upload project. Run upload_document/setup/create_document_manager_table.sql in your upload Supabase project SQL editor.'
        : 'uploaded but failed to persist metadata: ' + (insertError.message || String(insertError))
      return res.status(500).json({ error: msg })
    }

    console.log('[upload_document] Upload complete, document saved', { document_id: docId, storagePath })
    return res.json({ success: true, document_id: docId, storage_path: storagePath, bucket })
  } catch (err) {
    console.error('[upload_document] Unexpected error in upload endpoint:', err)
    return res.status(500).json({ error: String(err) })
  }
})

// Serve static frontend
const staticDir = path.join(__dirname, '..', 'frontend')
app.use(express.static(staticDir))

// Fallback to index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(staticDir, 'index.html'))
})

const PORT = process.env.PORT ? Number(process.env.PORT) : 5173
app.listen(PORT, () => {
  console.log(`[upload_document] UI server listening on http://localhost:${PORT}`)
  console.log('[upload_document] Serving static from', staticDir)
})
