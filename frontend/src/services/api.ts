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

    const url = resolveUrl(input)
    let res: Response
    try {
        res = await fetch(url, {
            ...init,
            headers,
        })
    } catch (e: unknown) {
        const rawMsg =
            e && typeof e === 'object' && 'message' in e
                ? String((e as { message?: unknown }).message ?? '')
                : String(e ?? '')
        const msg = rawMsg && rawMsg.trim() ? rawMsg.trim() : '网络请求失败'
        // 这类错误通常是：后端进程崩溃/连接被重置/CORS/端口不通，此时前端拿不到后端 JSON detail。
        throw new Error(`${msg}（${url}）。后端可能在返回响应前异常退出，请查看后端控制台日志。`)
    }

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
            const text = await res.text()
            const trimmed = text.trim()
            if (trimmed) {
                try {
                    const raw = JSON.parse(trimmed) as { detail?: unknown; message?: unknown }
                    const detail = raw?.detail ?? raw?.message
                    if (typeof detail === 'string' && detail.trim()) msg = detail.trim()
                    else msg = trimmed
                } catch {
                    msg = trimmed
                }
            }
        } catch {
            // ignore
        }
        throw new Error(msg)
    }
    return (await res.json()) as T
}
