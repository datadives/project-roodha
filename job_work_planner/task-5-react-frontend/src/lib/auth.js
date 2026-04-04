import { fetchAuthSession, getCurrentUser, signIn, signOut } from 'aws-amplify/auth'

export async function login(email, password) {
  return signIn({ username: email, password })
}

export async function logout() {
  return signOut()
}

export async function getAuthContext() {
  const user = await getCurrentUser()
  const session = await fetchAuthSession()
  const idToken = session.tokens?.idToken?.toString()
  const payload = session.tokens?.idToken?.payload || {}

  return {
    user,
    token: idToken,
    tenant_id: payload['custom:tenant_id'] || payload['tenant_id'] || null,
    user_role: payload['custom:user_role'] || payload['user_role'] || payload['cognito:groups']?.[0] || null,
  }
}
