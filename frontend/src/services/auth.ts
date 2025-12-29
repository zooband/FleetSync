import { ref, computed } from 'vue'

export type Role = 'admin' | 'manager' | 'staff'

export type AuthInfo = {
    token: string
    role: Role
    personnelId?: number
    fleetId?: number
    displayName?: string
}

const STORAGE_KEY = 'fleetsync.auth'

function safeParseAuth(raw: string | null): AuthInfo | null {
    if (!raw) return null
    try {
        const obj = JSON.parse(raw) as Partial<AuthInfo>
        if (!obj || typeof obj !== 'object') return null
        if (typeof obj.token !== 'string' || obj.token.length === 0) return null
        if (obj.role !== 'admin' && obj.role !== 'manager' && obj.role !== 'staff') return null
        return obj as AuthInfo
    } catch {
        return null
    }
}

export const auth = ref<AuthInfo | null>(safeParseAuth(localStorage.getItem(STORAGE_KEY)))

export const isLoggedIn = computed(() => !!auth.value?.token)

export function setAuth(info: AuthInfo) {
    auth.value = info
    localStorage.setItem(STORAGE_KEY, JSON.stringify(info))
}

export function clearAuth() {
    auth.value = null
    localStorage.removeItem(STORAGE_KEY)
}

export function getHomePath(): string {
    const a = auth.value
    if (!a) return '/login'
    if (a.role === 'admin') return '/distribution'
    if (a.role === 'manager') return a.fleetId != null ? `/fleet/${a.fleetId}` : '/login'
    return a.personnelId != null ? `/personnels/${a.personnelId}` : '/login'
}

export function getMyInfoPath(): string {
    const a = auth.value
    return a?.personnelId != null ? `/personnels/${a.personnelId}` : '/login'
}

export function getMyFleetPath(): string {
    const a = auth.value
    return a?.fleetId != null ? `/fleet/${a.fleetId}` : '/login'
}
