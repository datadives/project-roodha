/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: amplify.js
 * 
 * 1) Purpose: Utility library or API client for amplify.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { Amplify } from 'aws-amplify'
import { CLIENT_ID, CONFIG, REGION, USER_POOL_ID } from '../config'

const loginWith = {
  email: true,
}

if (CONFIG.COGNITO_DOMAIN) {
  loginWith.oauth = {
    domain: CONFIG.COGNITO_DOMAIN,
    scopes: ['email', 'openid', 'profile', 'aws.cognito.signin.user.admin'],
    redirectSignIn: [CONFIG.REDIRECT_URL],
    redirectSignOut: [CONFIG.REDIRECT_URL],
    responseType: 'code',
  }
}

export const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: USER_POOL_ID,
      userPoolClientId: CLIENT_ID,
      authenticationFlowType: 'USER_PASSWORD_AUTH',
      loginWith,
      region: REGION,
    },
  },
}

Amplify.configure(amplifyConfig)
