import readline from 'node:readline';
import { createClient } from '@supabase/supabase-js';

// This script signs in with email/password and prints the organization id.
// Behavior:
// 1. Sign in via Supabase Auth using provided credentials.
// 2. Try to read org_id from user.user_metadata.org_id
// 3. If absent, query the `UserProfiles` table for org_id where id = user.id

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Please set SUPABASE_URL and SUPABASE_KEY environment variables.');
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, { auth: { persistSession: false } });

function ask(question, mask = false) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    if (!mask) {
      rl.question(question, (ans) => {
        rl.close();
        resolve(ans.trim());
      });
    } else {
      // rudimentary hidden input for password
      const stdin = process.stdin;
      process.stdout.write(question);
      stdin.setRawMode(true);
      let value = '';
      stdin.on('data', function onData(ch) {
        ch = String(ch);
        if (ch === '\n' || ch === '\r' || ch === '\u0004') {
          stdin.setRawMode(false);
          process.stdout.write('\n');
          stdin.removeListener('data', onData);
          resolve(value);
        } else if (ch === '\u0003') {
          // Ctrl+C
          process.exit();
        } else if (ch === '\u0008' || ch === '\u007f') {
          // backspace
          value = value.slice(0, -1);
        } else {
          value += ch;
        }
      });
    }
  });
}

async function main() {
  try {
    const email = await ask('Email: ');
    const password = await ask('Password: ', true);

    console.log('\nSigning in...');

    const { data: signInData, error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (signInError) {
      console.error('Sign-in error:', signInError.message || signInError);
      process.exit(2);
    }

    const user = signInData?.user;
    if (!user) {
      console.error('Sign-in did not return a user object.');
      process.exit(3);
    }

    console.log('Signed in as:', user.email || user.id);

    // Try to resolve org_id from user metadata
    const orgFromMeta = user.user_metadata?.org_id;
    if (orgFromMeta) {
      console.log('Organization id (from user metadata):', orgFromMeta);
      process.exit(0);
    }

    // Fallback: query UserProfiles table where id = user.id
    console.log('org_id not found in user metadata, querying UserProfiles table...');
    const { data: profiles, error: profileError } = await supabase
      .from('UserProfiles')
      .select('org_id')
      .eq('id', user.id)
      .limit(1)
      .maybeSingle();

    if (profileError) {
      console.error('Error querying UserProfiles:', profileError.message || profileError);
      process.exit(4);
    }

    if (profiles && profiles.org_id) {
      console.log('Organization id (from UserProfiles):', profiles.org_id);
    } else {
      console.log('Organization id not found for this user.');
    }
  } catch (err) {
    console.error('Unexpected error:', err);
    process.exit(99);
  }
}

main();
