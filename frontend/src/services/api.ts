import { auth, clearAuth } from './auth'

type ApiFetchOptions = {
    auth?: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function resolveUrl(input: string): string {
    if (/^https?:\/\//i.test(input)) return input
    if (input.startsWith('/')) return `${API_BASE}${input}`
    return `${API_BASE}/${input}`
}

export async function apiFetch(
    input: string,
    init: RequestInit = {},
    options: ApiFetchOptions = {},
): Promise<Response> {
    const useAuth = options.auth !== false

    const headers = new Headers(init.headers)
    if (useAuth) {
        const token = auth.value?.token
        if (token) headers.set('Authorization', `Bearer ${token}`)
    }

    const res = await fetch(resolveUrl(input), {
        ...init,
        headers,
    })

    if (res.status === 401) {
        // token 失效/未登录：清理本地状态，交给路由守卫去跳转
        clearAuth()

        // 但如果当前页没有触发路由跳转，会停留在受限页面；这里直接强制回到登录页
        // 避免后端重启导致 token store 丢失时“看起来像已登录”。
        try {
            const currentHash = typeof window !== 'undefined' ? window.location.hash : ''
            const currentPath = currentHash.startsWith('#') ? currentHash.slice(1) : currentHash
            const isAlreadyLogin = currentPath.startsWith('/login')
            const isLoginRequest = typeof input === 'string' && input.includes('/api/auth/login')
            if (!isAlreadyLogin && !isLoginRequest) {
                const redirect = encodeURIComponent(currentPath || '/')
                window.location.hash = `#/login?redirect=${redirect}`
            }
        } catch {
            // ignore
        }
    }

    return res
}

export async function apiJson<T>(
    input: string,
    init: RequestInit = {},
    options: ApiFetchOptions = {},
): Promise<T> {
    const res = await apiFetch(input, init, options)
    if (!res.ok) {
        let msg = `请求失败 (${res.status})`
        try {
            const raw = (await res.json()) as { detail?: string }
            if (raw?.detail) msg = raw.detail
        } catch {
            // ignore
        }
        throw new Error(msg)
    }
    return (await res.json()) as T
}
