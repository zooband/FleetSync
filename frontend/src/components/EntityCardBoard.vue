<script setup lang="ts" generic="T extends Record<string, unknown>, IdKey extends keyof T = any">
import { computed, ref, onMounted, toRefs, nextTick } from 'vue'
import PrimeDialog from 'primevue/dialog'
import PrimeButton from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import AutoComplete from 'primevue/autocomplete'
import Paginator from 'primevue/paginator'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { Columns, TableOperations } from '@/types'
import CardGrid from '@/components/CardGrid.vue'
import EntityCard from '@/components/EntityCard.vue'
import { apiFetch } from '@/services/api'

type ForeignOption = Record<string, unknown>
type FormValue = string | number | null | ForeignOption

const props = withDefaults(
    defineProps<{
        operations: TableOperations<T, IdKey>
        columns: readonly Columns[]
        createColumns?: readonly Columns[]
        editColumns?: readonly Columns[]
        titleKey: string
        click?: (item: T) => void
        allowCreate?: boolean
        allowEdit?: boolean
        allowDelete?: boolean
        canDeleteItem?: (item: T) => boolean
        gridColumns?: 1 | 2 | 3 | 4
        confirmGroup?: string
    }>(),
    {
        allowCreate: true,
        allowEdit: true,
        allowDelete: true,
        gridColumns: 4,
    }
)

const { operations, columns, allowCreate, allowEdit, allowDelete, gridColumns } = toRefs(props)

const toast = useToast()
const confirm = useConfirm()

const idField = computed<string | undefined>(() => columns.value.find(c => c.isId)?.key)

const pageRows = ref(12)
const pageFirst = ref(0)
const queryText = ref('')

const recordCount = computed(() => operations.value.total ?? operations.value.data?.length ?? 0)
const currentData = computed<readonly T[]>(() => operations.value.data ?? [])

const createVisible = ref(false)
const editVisible = ref(false)
const submitting = ref(false)
const refreshing = ref(false)

const createForm = ref<Record<string, FormValue>>({})
const editForm = ref<Record<string, FormValue>>({})
const editingItem = ref<T | null>(null)
const editingOriginalId = ref<T[IdKey] | null>(null)

const createColumnsResolved = computed(() => props.createColumns ?? columns.value)
const editColumnsResolved = computed(() => props.editColumns ?? columns.value)

const createFormFields = computed(() => createColumnsResolved.value.filter(c => c.editable))
const editFormFields = computed(() => editColumnsResolved.value.filter(c => c.editable))

// 确认框分组：每个实例唯一，避免同页多实例同时弹窗
const confirmGroupResolved = computed(() => props.confirmGroup ?? `entity-card-delete-${props.titleKey}`)

const foreignSuggestions = ref<Record<string, ForeignOption[]>>({})

function isForeignField(field: Columns): boolean {
    return field.type === 'foreign' && !!field.foreign
}

function getForeignId(field: Columns, value: FormValue | undefined): string | number | null {
    if (!isForeignField(field)) return (value as string | number | null | undefined) ?? null
    if (value == null) return null
    if (typeof value === 'string' || typeof value === 'number') return value
    const key = field.foreign!.valueKey
    const raw = (value as ForeignOption)[key]
    if (typeof raw === 'string' || typeof raw === 'number') return raw
    return raw == null ? null : String(raw)
}

async function completeForeign(field: Columns, query: string) {
    if (!isForeignField(field)) return
    const cfg = field.foreign!
    const qp = cfg.queryParam ?? 'q'
    const lp = cfg.limitParam ?? 'limit'
    const op = cfg.offsetParam ?? 'offset'

    // 这里用小分页拉候选，满足“延迟后出现匹配下拉列表”的交互
    const params = new URLSearchParams({
        [qp]: query,
        [lp]: '10',
        [op]: '0',
    })

    const url = cfg.endpoint.includes('?') ? `${cfg.endpoint}&${params}` : `${cfg.endpoint}?${params}`
    const res = await apiFetch(url)
    if (!res.ok) throw new Error('加载候选失败')

    const raw = (await res.json()) as unknown
    const rows = Array.isArray(raw)
        ? (raw as ForeignOption[])
        : (((raw as { data?: ForeignOption[] })?.data ?? raw) as ForeignOption[])

    foreignSuggestions.value[field.key] = rows ?? []
}

function showSuccess(message: string) {
    toast.add({ severity: 'success', summary: '成功', detail: message, life: 1500 })
}

function showError(message: string) {
    toast.add({ severity: 'error', summary: '错误', detail: message })
}

function getItemIdValue(item: Record<string, unknown>): T[IdKey] | undefined {
    if (!idField.value) return undefined
    const key = item[idField.value] as T[IdKey] | null | undefined
    return key == null ? undefined : key
}

function asString(value: FormValue | undefined): string | null {
    return value == null ? null : String(value)
}

function asNumber(value: FormValue | undefined): number | null {
    if (value == null) return null
    const num = typeof value === 'number' ? value : Number(value)
    return Number.isNaN(num) ? null : num
}

function setCreateTextValue(fieldKey: string, value: string | null | undefined) {
    createForm.value[fieldKey] = (value ?? '') as FormValue
}

function setCreateNumberValue(fieldKey: string, value: number | null | undefined) {
    createForm.value[fieldKey] = (value ?? null) as FormValue
}

function setCreateSelectValue(fieldKey: string, value: string | null | undefined) {
    createForm.value[fieldKey] = (value ?? '') as FormValue
}

function setEditTextValue(fieldKey: string, value: string | null | undefined) {
    editForm.value[fieldKey] = (value ?? '') as FormValue
}

function setEditNumberValue(fieldKey: string, value: number | null | undefined) {
    editForm.value[fieldKey] = (value ?? null) as FormValue
}

function setEditSelectValue(fieldKey: string, value: string | null | undefined) {
    editForm.value[fieldKey] = (value ?? '') as FormValue
}

function validateRequired(form: Record<string, FormValue>, fields: readonly Columns[]): string[] {
    return fields
        .filter(col => col.required !== false)
        .filter(col => {
            const v = form[col.key]
            if (col.type === 'number') return v == null || (typeof v === 'number' && Number.isNaN(v))
            if (col.type === 'foreign') {
                const id = getForeignId(col, v)
                return id == null || String(id).trim().length === 0
            }
            const s = v == null ? '' : String(v)
            return s.trim().length === 0
        })
        .map(col => col.label)
}

function buildSubmitPayload(form: Record<string, FormValue>, fields: readonly Columns[]): Record<string, unknown> {
    const payload: Record<string, unknown> = {}
    for (const field of fields) {
        const v = form[field.key]
        if (field.type === 'foreign') {
            payload[field.key] = getForeignId(field, v)
        } else {
            payload[field.key] = v
        }
    }
    return payload
}

function buildSubtitleLines(item: T): string[] {
    const titleKey = props.titleKey
    return columns.value
        .filter(c => c.key !== titleKey)
        .map(c => {
            const v = (item as Record<string, unknown>)[c.key]
            const text = v == null ? '' : String(v)
            return `${c.label}：${text}`
        })
}

function getTitle(item: T): string {
    const v = (item as Record<string, unknown>)[props.titleKey]
    return v == null ? '' : String(v)
}

async function fetchByQuery() {
    await operations.value.search(queryText.value, pageRows.value, pageFirst.value)
}

async function refresh() {
    refreshing.value = true
    await nextTick()
    const started = performance.now()
    try {
        await fetchByQuery()
    } catch (e) {
        showError((e as Error).message || '刷新失败')
    } finally {
        const minMs = 300
        const elapsed = performance.now() - started
        if (elapsed < minMs) {
            await new Promise(r => setTimeout(r, minMs - elapsed))
        }
        refreshing.value = false
    }
}

function onPage(event: { first: number; rows: number }) {
    pageFirst.value = event.first
    pageRows.value = event.rows
    fetchByQuery().catch((e) => {
        showError((e as Error).message || '分页加载失败')
    })
}

function openCreate() {
    if (!operations.value.create) return
    createForm.value = createFormFields.value.reduce<Record<string, FormValue>>(
        (acc, field) => ({
            ...acc,
            [field.key]:
                field.type === 'number'
                    ? 0
                    : field.type === 'select'
                        ? (field.options?.[0] ?? '')
                        : field.type === 'foreign'
                            ? null
                            : '',
        }),
        {}
    )
    createVisible.value = true
}

async function confirmCreate() {
    const createOp = operations.value.create
    if (!createOp) return
    const missing = validateRequired(createForm.value, createFormFields.value)
    if (missing.length > 0) {
        showError(`请填写必填项：${missing.join('、')}`)
        return
    }

    submitting.value = true
    try {
        const payload = buildSubmitPayload(createForm.value, createFormFields.value)
        await createOp(payload as Partial<T>)
        createVisible.value = false
        showSuccess('添加成功')
        await fetchByQuery()
    } catch (e) {
        showError((e as Error).message || '添加失败')
    } finally {
        submitting.value = false
    }
}

function openEdit(item: T) {
    if (!operations.value.update) return
    editingItem.value = item
    editingOriginalId.value = (getItemIdValue(item as Record<string, unknown>) as T[IdKey] | undefined) ?? null

    const form = editFormFields.value.reduce<Record<string, FormValue>>((acc, col) => {
        const v = (item as Record<string, unknown>)[col.key]
        if (col.type === 'number') acc[col.key] = typeof v === 'number' ? v : (v == null ? null : Number(v))
        else if (col.type === 'foreign') {
            // 编辑时如果后端没给出 name，只能先显示 id（用户可重新搜索选择）
            const id = v == null ? null : (typeof v === 'number' || typeof v === 'string' ? v : String(v))
            acc[col.key] = id == null
                ? null
                : ({
                    [col.foreign?.valueKey ?? 'id']: id,
                    [col.foreign?.labelKey ?? 'label']: String(id),
                } as ForeignOption)
        }
        else acc[col.key] = v == null ? '' : String(v)
        return acc
    }, {})

    editForm.value = form

    editVisible.value = true
}

async function confirmEdit() {
    const updateOp = operations.value.update
    if (!updateOp) return
    const item = editingItem.value
    if (!item) return

    const missing = validateRequired(editForm.value, editFormFields.value)
    if (missing.length > 0) {
        showError(`请填写必填项：${missing.join('、')}`)
        return
    }

    const lookupId = (editingOriginalId.value ?? (getItemIdValue(item as Record<string, unknown>) as T[IdKey] | undefined))

    if (lookupId == null) {
        showError('当前数据无主键，无法编辑')
        return
    }

    submitting.value = true
    try {
        const payload = buildSubmitPayload(editForm.value, editFormFields.value)
        await updateOp(lookupId, payload as Partial<T>)
        editVisible.value = false
        editingItem.value = null
        editingOriginalId.value = null
        showSuccess('更新成功')
        await fetchByQuery()
    } catch (e) {
        showError((e as Error).message || '更新失败')
    } finally {
        submitting.value = false
    }
}

function doDelete(item: T) {
    const deleteOp = operations.value.delete
    if (!deleteOp) return

    const idValue = getItemIdValue(item as Record<string, unknown>)
    if (idValue == null) {
        showError('当前数据无主键，无法删除')
        return
    }

    const name = getTitle(item) || '该记录'

    confirm.require({
        message: `确定删除 "${name}"？`,
        group: confirmGroupResolved.value,
        acceptLabel: '确认',
        rejectLabel: '取消',
        acceptClass: 'p-button-danger',
        accept: async () => {
            try {
                await deleteOp(idValue)
                showSuccess('删除成功')
                await fetchByQuery()
            } catch (e) {
                showError((e as Error).message || '删除失败')
            }
        },
    })
}

onMounted(() => {
    fetchByQuery().catch((e) => {
        showError((e as Error)?.message || String(e) || '初始化加载失败')
    })
})
</script>

<template>
    <div class="space-y-4">

        <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500">共 {{ recordCount }} 条记录，当前显示 {{ currentData.length }} 条</span>
            <div class="flex gap-2">
                <PrimeButton label="刷新" icon="pi pi-refresh" :loading="refreshing" :disabled="refreshing"
                    @click="refresh" />
            </div>
        </div>

        <CardGrid :columns="gridColumns">
            <EntityCard v-for="item in currentData"
                :key="idField ? String((item as Record<string, unknown>)[idField]) : getTitle(item)"
                :title="getTitle(item)" :subtitleLines="buildSubtitleLines(item)"
                :allowEdit="allowEdit && !!operations.update"
                :allowDelete="allowDelete && !!operations.delete && (props.canDeleteItem ? props.canDeleteItem(item) : true)"
                @click="click?.(item)" @edit="openEdit(item)" @delete="doDelete(item)">
                <template v-if="$slots.cardActions" #actions>
                    <slot name="cardActions" :item="item" />
                </template>
            </EntityCard>

            <EntityCard v-if="allowCreate && !!operations.create" variant="add" title="" :clickable="true"
                :allowEdit="false" :allowDelete="false" @click="openCreate" />
        </CardGrid>

        <Paginator :rows="pageRows" :first="pageFirst" :totalRecords="recordCount" :rowsPerPageOptions="[12, 24, 48]"
            @page="onPage" />

        <PrimeDialog v-model:visible="createVisible" modal header="新增" :style="{ width: '50rem' }">
            <div class="grid grid-cols-2 gap-4">
                <div v-for="field in createFormFields" :key="field.key" class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {{ field.label }}<span v-if="field.required !== false">*</span>
                    </label>

                    <template v-if="field.type === 'text'">
                        <InputText :modelValue="asString(createForm[field.key])"
                            @update:modelValue="setCreateTextValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'number'">
                        <InputNumber :modelValue="asNumber(createForm[field.key])" mode="decimal" :maxFractionDigits="2"
                            class="w-full" @update:modelValue="setCreateNumberValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'foreign'">
                        <AutoComplete v-model="createForm[field.key]" class="w-full" :delay="300" :forceSelection="true"
                            inputClass="w-full" :suggestions="foreignSuggestions[field.key] ?? []"
                            :optionLabel="field.foreign?.labelKey" @complete="completeForeign(field, $event.query)"
                            :min-length="0" :complete-on-focus="true"
                            @item-select="() => { /* v-model already updated */ }">
                            <template #option="{ option }">
                                <div class="flex flex-col">
                                    <span>{{ field.foreign?.labelKey ? String(option?.[field.foreign.labelKey] ?? '') :
                                        '' }}</span>
                                    <span class="text-xs text-gray-500">{{ field.foreign?.valueKey ?
                                        String(option?.[field.foreign.valueKey] ?? '') : '' }}</span>
                                </div>
                            </template>
                        </AutoComplete>
                    </template>
                    <template v-else>
                        <Select :modelValue="asString(createForm[field.key])"
                            :options="field.options ? [...field.options] : []" class="w-full"
                            @update:modelValue="setCreateSelectValue(field.key, $event)" />
                    </template>
                </div>
            </div>

            <template #footer>
                <PrimeButton label="取消" severity="secondary" @click="createVisible = false" />
                <PrimeButton label="确认" :loading="submitting" @click="confirmCreate" />
            </template>
        </PrimeDialog>

        <PrimeDialog v-model:visible="editVisible" modal header="编辑" :style="{ width: '50rem' }">
            <div class="grid grid-cols-2 gap-4">
                <div v-for="field in editFormFields" :key="field.key" class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {{ field.label }}<span v-if="field.required !== false">*</span>
                    </label>

                    <template v-if="field.type === 'text'">
                        <InputText :modelValue="asString(editForm[field.key])"
                            @update:modelValue="setEditTextValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'number'">
                        <InputNumber :modelValue="asNumber(editForm[field.key])" mode="decimal" :maxFractionDigits="2"
                            class="w-full" @update:modelValue="setEditNumberValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'foreign'">
                        <AutoComplete v-model="editForm[field.key]" class="w-full" :delay="300" :forceSelection="true"
                            inputClass="w-full" :suggestions="foreignSuggestions[field.key] ?? []"
                            :optionLabel="field.foreign?.labelKey" @complete="completeForeign(field, $event.query)"
                            :min-length="0" :complete-on-focus="true">
                            <template #option="{ option }">
                                <div class="flex flex-col">
                                    <span>{{ field.foreign?.labelKey ? String(option?.[field.foreign.labelKey] ?? '') :
                                        '' }}</span>
                                    <span class="text-xs text-gray-500">{{ field.foreign?.valueKey ?
                                        String(option?.[field.foreign.valueKey] ?? '') : '' }}</span>
                                </div>
                            </template>
                        </AutoComplete>
                    </template>
                    <template v-else>
                        <Select :modelValue="asString(editForm[field.key])"
                            :options="field.options ? [...field.options] : []" class="w-full"
                            @update:modelValue="setEditSelectValue(field.key, $event)" />
                    </template>
                </div>
            </div>

            <template #footer>
                <PrimeButton label="取消" severity="secondary" @click="editVisible = false" />
                <PrimeButton label="确认" :loading="submitting" @click="confirmEdit" />
            </template>
        </PrimeDialog>
        <!-- 删除确认框（分组），固定宽度 -->
        <ConfirmDialog :group="confirmGroupResolved" :style="{ width: '32rem' }" />
    </div>
</template>
