/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: roles.js
 * 
 * 1) Purpose: Utility library or API client for roles.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

const ALL_ACCESS_ROLES = ['OWNER']

const permissionMatrix = {
  OWNER: [
    'dashboard',
    'jobs',
    'masterData',
    'masterDataWrite',
    'analytics',
    'machineLoad',
    'autoSchedule',
    'worklist',
    'exports',
    'settings',
    'userManagement',
    'financialConfig',
    'notifications',
    'plan',
    'overridePlan',
    'execute',
  ],
  SUPERVISOR: [
    'dashboard',
    'jobs',
    'masterData',
    'machineLoad',
    'autoSchedule',
    'worklist',
    'exports',
    'notifications',
    'plan',
    'execute',
  ],
  OPERATOR: ['operatorDashboard', 'worklist', 'notifications', 'execute'],
}

const roleLabels = {
  OWNER: 'Owner',
  SUPERVISOR: 'Supervisor',
  OPERATOR: 'Operator',
}

export function normalizeRole(role) {
  const normalizedRole = role ? role.toString().trim().toUpperCase() : ''
  return normalizedRole === 'WORKER' ? 'OPERATOR' : normalizedRole
}

export function getRoleLabel(role) {
  const normalizedRole = normalizeRole(role)
  return roleLabels[normalizedRole] || normalizedRole || 'Unassigned'
}

export function hasAnyRole(role, allowedRoles = []) {
  const normalizedRole = normalizeRole(role)
  if (!normalizedRole || allowedRoles.length === 0) {
    return false
  }

  return allowedRoles.map(normalizeRole).includes(normalizedRole)
}

export function hasPermission(role, permission) {
  const normalizedRole = normalizeRole(role)
  if (!normalizedRole || !permission) {
    return false
  }

  if (ALL_ACCESS_ROLES.includes(normalizedRole)) {
    return true
  }

  return permissionMatrix[normalizedRole]?.includes(permission) || false
}

export function getDefaultRouteForRole(role) {
  return hasPermission(role, 'operatorDashboard') ? '/operator' : '/dashboard'
}

export function listAllowedRoleLabels(roles = []) {
  return roles.map((role) => getRoleLabel(role)).join(', ')
}
