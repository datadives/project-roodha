const ALL_ACCESS_ROLES = ['OWNER', 'ADMIN']

const permissionMatrix = {
  OWNER: ['dashboard', 'jobs', 'masterData', 'analytics', 'notifications', 'plan', 'overridePlan', 'execute'],
  ADMIN: ['dashboard', 'jobs', 'masterData', 'analytics', 'notifications', 'plan', 'overridePlan', 'execute'],
  SUPERVISOR: ['dashboard', 'jobs', 'masterData', 'analytics', 'notifications', 'plan', 'overridePlan', 'execute'],
  PLANNER: ['dashboard', 'analytics', 'notifications', 'plan'],
  OPERATOR: ['dashboard', 'notifications', 'execute'],
}

const roleLabels = {
  OWNER: 'Owner',
  ADMIN: 'Admin',
  SUPERVISOR: 'Supervisor',
  PLANNER: 'Planner',
  OPERATOR: 'Operator',
}

export function normalizeRole(role) {
  return role ? role.toString().trim().toUpperCase() : ''
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
  return hasPermission(role, 'dashboard') ? '/' : '/notifications'
}

export function listAllowedRoleLabels(roles = []) {
  return roles.map((role) => getRoleLabel(role)).join(', ')
}
