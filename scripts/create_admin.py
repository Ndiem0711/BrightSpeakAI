"""One-time privileged initial administrator provisioning; invoke from trusted environment.

Pass DATABASE_URL and SECRET_KEY through environment or Secret Manager,
not arguments, and run only when a secure DB connection is available.
"""
import getpass
import os
import uuid

from app.auth import hash_password, iso_now
from app.db import db


def main():
    print('BrightSpeak AI - initial administrator account setup')
    email = input('Administrator email: ').strip().lower()
    if not email or '@' not in email: raise SystemExit('Invalid administrator email')
    full_name = input('Full name: ').strip()
    if len(full_name)<2: raise SystemExit('Name too short')
    password = getpass.getpass('Password (12+ characters): ')
    if len(password)<12: raise SystemExit('Password must have at least 12 characters')
    db.init_schema()
    if db.fetchone('SELECT id FROM users WHERE email=?',(email,)):
        raise SystemExit('Email already exists: cannot overwrite existing account')
    db.execute('''INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at)
                  VALUES(?,?,?,?,?,?,?,?,?)''',
               (str(uuid.uuid4()), email, hash_password(password), full_name, 'admin', None, 1, 1, iso_now()))
    print('Created administrator. Do not share these credentials.')

if __name__=='__main__':main()
