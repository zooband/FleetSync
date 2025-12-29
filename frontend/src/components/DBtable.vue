<script setup lang="ts" generic="T extends Record<string, unknown>, IdKey extends keyof T = any">
import { ref, computed, watch, onMounted, toRefs, nextTick } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import AutoComplete from 'primevue/autocomplete'
import DatePicker from 'primevue/datepicker'
import PrimeButton from 'primevue/button'
import PrimeDialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { Columns, TableOperations } from '@/types'
import { apiFetch } from '@/services/api'

type ForeignOption = Record<string, unknown>

const props = withDefaults(
    defineProps<{
        operations: TableOperations<T, IdKey>
        columns: readonly Columns[]
        allowCreate?: boolean
        allowEdit?: boolean
        allowDelete?: boolean
    }>(),
    {
        allowCreate: true,
        allowEdit: true,
        allowDelete: true,
    }
)

const { operations, columns, allowCreate, allowEdit, allowDelete } = toRefs(props)

const createVisible = ref(false)
const submitting = ref(false)
const refreshing = ref(false)
const pageRows = ref(10)
const pageFirst = ref(0)

type FormValue = string | number | Date | ForeignOption | null
const createForm = ref<Record<string, FormValue>>({})

const editingRows = ref<T[]>([])
const originalDataMap = ref<Record<string, T>>({})
const foreignSuggestions = ref<Record<string, ForeignOption[]>>({})
const localSuggestions = ref<Record<string, string[]>>({})

function filterLocalSuggestions(options: readonly string[], query: string): string[] {
    const q = (query ?? '').trim().toLowerCase()
    if (!q) return [...options]
    return options.filter(o => String(o).toLowerCase().includes(q))
}

function completeLocalSuggestions(key: string, options: readonly string[], query: string) {
    localSuggestions.value[key] = filterLocalSuggestions(options, query)
}

const toast = useToast()
const confirm = useConfirm()

const recordCount = computed(() => operations.value.total ?? operations.value.data?.length ?? 0)

const currentData = computed<T[]>(() => operations.value.data ?? [])

const idField = computed<string | undefined>(() => columns.value.find(col => col.isId)?.key)

const dataKey = computed<string | undefined>(() => {
    return hasRowId.value && idField.value ? idField.value : undefined
})

const hasRowId = computed(() => {
    if (!idField.value) return false
    if (currentData.value.length === 0) return true
    return currentData.value.every((row) => (row as Record<string, unknown>)[idField.value!] != null)
})

const editableEnabled = computed(() => allowEdit.value !== false && hasRowId.value && !!operations.value.update)

const deletableEnabled = computed(() => allowDelete.value !== false && hasRowId.value && !!operations.value.delete)

const createFormFields = computed(() => columns.value.filter(col => col.editable))

const ORIGINAL_ID_FIELD = '__originalId' as const

function getOriginalIdTextFromRow(row: unknown): string | undefined {
    const v = (row as Record<string, unknown>)[ORIGINAL_ID_FIELD]
    return typeof v === 'string' && v.length > 0 ? v : undefined
}

function setOriginalIdTextToRow(row: unknown, idText: string) {
    ; (row as Record<string, unknown>)[ORIGINAL_ID_FIELD] = idText
}

function clearOriginalIdTextFromRow(row: unknown) {
    delete (row as Record<string, unknown>)[ORIGINAL_ID_FIELD]
}

function stripInternalFields(obj: Record<string, unknown>) {
    delete obj[ORIGINAL_ID_FIELD]
}

function getItemIdValue(item: Record<string, unknown>): T[IdKey] | undefined {
    if (!idField.value) return undefined
    const key = item[idField.value] as T[IdKey] | null | undefined
    return key == null ? undefined : key
}

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

    const params = new URLSearchParams({ [qp]: query, [lp]: '10', [op]: '0' })
    const url = cfg.endpoint.includes('?') ? `${cfg.endpoint}&${params}` : `${cfg.endpoint}?${params}`
    const res = await apiFetch(url)
    if (!res.ok) throw new Error('加载候选失败')

    const raw = (await res.json()) as unknown
    const rows = Array.isArray(raw)
        ? (raw as ForeignOption[])
        : (((raw as { data?: ForeignOption[] })?.data ?? raw) as ForeignOption[])
    foreignSuggestions.value[field.key] = rows ?? []
}

function toDateString(value: unknown): string {
    if (value instanceof Date) {
        const y = value.getFullYear()
        const m = `${value.getMonth() + 1}`.padStart(2, '0')
        const d = `${value.getDate()}`.padStart(2, '0')
        return `${y}-${m}-${d}`
    }
    if (typeof value === 'string') return value
    return ''
}

function toDateModel(value: unknown): Date | null {
    if (value instanceof Date) return value
    if (typeof value === 'string' && value) return new Date(value)
    return null
}

function normalizePayload(fields: readonly Columns[], source: Record<string, FormValue>): Record<string, unknown> {
    const payload: Record<string, unknown> = {}
    for (const field of fields) {
        const v = source[field.key]
        if (field.type === 'foreign') payload[field.key] = getForeignId(field, v)
        else if (field.type === 'date') payload[field.key] = v == null ? null : toDateString(v)
        else payload[field.key] = v
    }
    return payload
}

function getItemIdText(item: Record<string, unknown>): string | undefined {
    const id = getItemIdValue(item)
    return id == null ? undefined : String(id)
}

function asString(value: FormValue | undefined): string | null {
    return value == null ? null : String(value)
}

function asNumber(value: FormValue | undefined): number | null {
    if (value == null) return null
    const num = typeof value === 'number' ? value : Number(value)
    return isNaN(num) ? null : num
}

function showSuccess(message: string) {
    toast.add({ severity: 'success', summary: '成功', detail: message, life: 1500 })
}

function showError(message: string) {
    toast.add({ severity: 'error', summary: '错误', detail: message })
}

function displayValue(row: Record<string, unknown>, col: Columns): string {
    const v = row[col.key]
    if (col.type === 'date') return toDateString(v)
    if (col.type === 'foreign') {
        if (v && typeof v === 'object' && !Array.isArray(v)) {
            const labelKey = col.foreign?.labelKey
            if (labelKey && (v as Record<string, unknown>)[labelKey] != null) {
                return String((v as Record<string, unknown>)[labelKey])
            }
        }
        return String(v ?? '')
    }
    return String(v ?? '')
}

function setRowTextValue(data: unknown, field: string, value: string | null | undefined) {
    ; (data as Record<string, FormValue>)[field] = (value ?? '') as FormValue
}

function setRowNumberValue(data: unknown, field: string, value: number | null | undefined) {
    ; (data as Record<string, FormValue>)[field] = (value ?? null) as FormValue
}

function setRowSelectValue(data: unknown, field: string, value: string | null | undefined) {
    ; (data as Record<string, FormValue>)[field] = (value ?? '') as FormValue
}

function setRowDateValue(data: unknown, field: string, value: Date | null | undefined) {
    ; (data as Record<string, FormValue>)[field] = (value ?? null) as FormValue
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

function setCreateDateValue(fieldKey: string, value: Date | null | undefined) {
    createForm.value[fieldKey] = (value ?? null) as FormValue
}

function onRowEditInit(event: { data: T }) {
    const item = event.data
    const idText = getItemIdText(item as unknown as Record<string, unknown>)
    if (!idText) {
        showError('当前数据无主键，无法进入编辑')
        return
    }
    // 记录原始数据并把原始主键保存到行对象上，便于后续在编辑时恢复或用于更新识别
    originalDataMap.value[idText] = { ...(item as T) }
    setOriginalIdTextToRow(item, idText)
}

function onRowEditCancel(event: { data: T }) {
    const item = event.data
    // 优先使用保存的原始主键标识来恢复（兼容主键被用户修改的情况）
    const origId = getOriginalIdTextFromRow(item) ?? getItemIdText(item as unknown as Record<string, unknown>)
    if (!origId) return

    const original = originalDataMap.value[origId]
    if (!original) return

    Object.assign(item as unknown as Record<string, unknown>, original as unknown as Record<string, unknown>)
    // 清理临时存储
    clearOriginalIdTextFromRow(item)
    delete originalDataMap.value[origId]
}

async function onRowEditSave(event: { data: T; newData: T }) {
    const item = event.newData ?? event.data
    // 支持修改主键场景：使用编辑开始时保存的原始主键作为查找 id，更新内容中包含新的主键值
    const originalIdText = getOriginalIdTextFromRow(event.data)
    const original = originalIdText ? originalDataMap.value[originalIdText] : undefined
    const originalIdValue = original ? getItemIdValue(original as unknown as Record<string, unknown>) : undefined
    const newIdValue = getItemIdValue(item as unknown as Record<string, unknown>)

    if (originalIdValue == null && newIdValue == null) {
        showError('当前数据无主键，无法保存编辑')
        return
    }

    try {
        const restRaw = { ...(item as unknown as Record<string, FormValue>) }
        stripInternalFields(restRaw as Record<string, unknown>)
        const rest = normalizePayload(columns.value, restRaw)
        // 不再删除主键字段：如果用户修改了主键，新的主键应包含在更新内容中，后端可据此修改主键。

        const updateOp = operations.value.update
        if (updateOp) {
            // 使用原始主键（若有）作为查找 id，否则使用当前主键
            const lookupId = originalIdValue ?? newIdValue
            await updateOp(lookupId as T[IdKey], rest as Partial<T>)
            showSuccess('更新成功')
            // 清理原始数据存储
            if (originalIdText) {
                delete originalDataMap.value[originalIdText]
            }
            clearOriginalIdTextFromRow(event.data)
            await fetchByQuery()
        }
    } catch (error) {
        // 恢复到原始数据
        const origKey = getOriginalIdTextFromRow(event.data)
        const originalBackup = origKey ? originalDataMap.value[origKey] : undefined
        if (originalBackup) Object.assign(item as unknown as Record<string, unknown>, originalBackup as unknown as Record<string, unknown>)
        showError(`更新失败: ${error}`)
    }
}

function doDelete(item: Record<string, unknown>) {
    const deleteOp = operations.value.delete
    if (!deleteOp) return

    const idValue = getItemIdValue(item)
    if (idValue == null) {
        showError('当前数据无主键，无法删除')
        return
    }

    const firstField = columns.value[0]?.key
    const name = firstField ? String(item[firstField] ?? '该记录') : '该记录'

    confirm.require({
        message: `确定删除 "${name}"？`,
        group: 'dbtable-delete',
        acceptLabel: '确认',
        rejectLabel: '取消',
        acceptClass: 'p-button-danger',
        accept: async () => {
            try {
                await deleteOp(idValue)
                showSuccess('删除成功')
                await fetchByQuery()
            } catch {
                showError('删除失败')
            }
        },
    })
}

async function doCreate() {
    const createOp = operations.value.create
    if (!createOp) return
    submitting.value = true
    try {
        const payload = normalizePayload(createFormFields.value, createForm.value)
        await createOp(payload as Partial<T>)
        createVisible.value = false
        resetCreate()
        showSuccess('添加成功')
        await fetchByQuery()
    } catch (error) {
        showError((error as Error).message || '添加失败')
    } finally {
        submitting.value = false
    }
}

function resetCreate() {
    createForm.value = createFormFields.value.reduce<Record<string, FormValue>>(
        (acc, field) => ({
            ...acc,
            [field.key]: field.type === 'number'
                ? 0
                : field.type === 'select'
                    ? (field.options?.[0] ?? '')
                    : field.type === 'date'
                        ? null
                        : field.type === 'foreign'
                            ? null
                            : '',
        }),
        {}
    )
}

async function fetchByQuery() {
    await operations.value.search('', pageRows.value, pageFirst.value)
}

async function refresh() {
    refreshing.value = true
    // 先让按钮进入 loading 再执行请求，避免“看不到转圈”
    await nextTick()
    const started = performance.now()
    try {
        await fetchByQuery()
    } catch (e: unknown) {
        showError('无法连接服务器，刷新失败')
        console.error('刷新失败：', e)
    } finally {
        // 保证最短显示时长，避免瞬间闪烁看不见
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
        showError('分页加载失败')
        console.error('分页加载失败：', e)
    })
}


onMounted(() => {
    // 初始化表单并加载第一页
    resetCreate()
    fetchByQuery().catch((e) => {
        showError('初始化加载失败')
        console.error('初始化加载失败：', e)
    })
})

watch(
    () => columns.value,
    () => {
        resetCreate()
    },
    { deep: true }
)

watch(
    () => createVisible.value,
    async (visible) => {
        if (!visible) return
        // 打开“添加记录”弹窗时，预取所有外键候选，避免“未输入就 No results found”
        const fields = createFormFields.value.filter(f => f.type === 'foreign')
        await Promise.all(
            fields.map(async (f) => {
                try {
                    await completeForeign(f, '')
                } catch (e) {
                    console.error('预取外键候选失败：', e)
                }
            })
        )
    }
)
</script>
<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500">共 {{ recordCount }} 条记录，当前显示 {{ currentData.length }} 条</span>
            <div class="flex gap-2">
                <PrimeButton label="刷新" icon="pi pi-refresh" :loading="refreshing" :disabled="refreshing"
                    @click="refresh" />
                <PrimeButton v-if="allowCreate" label="添加记录" icon="pi pi-plus" @click="createVisible = true" />
            </div>
        </div>

        <DataTable :value="currentData" :lazy="true" :paginator="true" :rows="pageRows" :totalRecords="recordCount"
            :rowsPerPageOptions="[10, 20, 50]" :dataKey="dataKey"
            paginatorTemplate="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
            responsiveLayout="scroll" editMode="row" v-model:editingRows="editingRows" @row-edit-init="onRowEditInit"
            @row-edit-cancel="onRowEditCancel" @row-edit-save="onRowEditSave" @page="onPage"
            :tableStyle="{ 'table-layout': 'fixed' }" class="p-datatable-sm w-full">
            <Column v-for="col in columns" :key="col.key" :field="col.key" :header="col.label">
                <!-- 显示内容 -->
                <template #body="{ data }">
                    {{ displayValue(data as Record<string, unknown>, col) }}
                </template>

                <!-- 编辑器（如果允许编辑） -->
                <template v-if="allowEdit && col.editable !== false" #editor="{ data, field }">
                    <template v-if="col.type === 'text'">
                        <AutoComplete v-if="Array.isArray(col.suggestions)" class="w-full" inputClass="w-full"
                            :modelValue="asString((data as Record<string, FormValue>)[field])" :forceSelection="false"
                            :dropdown="true" :minLength="0" :completeOnFocus="true"
                            :suggestions="localSuggestions[`__local_${String(field)}`] ?? filterLocalSuggestions(col.suggestions, '')"
                            @complete="(e) => completeLocalSuggestions(`__local_${String(field)}`, col.suggestions!, e.query)"
                            @update:modelValue="(v) => setRowTextValue(data, field, (v as any) ?? '')" />
                        <InputText v-else :modelValue="asString((data as Record<string, FormValue>)[field])"
                            class="w-full" @update:modelValue="setRowTextValue(data, field, $event)" />
                    </template>
                    <template v-else-if="col.type === 'number'">
                        <InputNumber :modelValue="asNumber((data as Record<string, FormValue>)[field])" mode="decimal"
                            :maxFractionDigits="2" class="w-full"
                            @update:modelValue="setRowNumberValue(data, field, $event)" />
                    </template>
                    <template v-else-if="col.type === 'date'">
                        <DatePicker :modelValue="toDateModel((data as Record<string, FormValue>)[field])"
                            dateFormat="yy-mm-dd" showIcon inputClass="w-full"
                            @update:modelValue="(v) => setRowDateValue(data, field, Array.isArray(v) ? (v[0] ?? null) : (v ?? null))" />
                    </template>
                    <template v-else-if="col.type === 'foreign'">
                        <AutoComplete v-model="(data as Record<string, FormValue>)[field]" class="w-full"
                            inputClass="w-full" :delay="300" :forceSelection="true"
                            :suggestions="foreignSuggestions[field] ?? []" :optionLabel="col.foreign?.labelKey"
                            @complete="completeForeign(col, $event.query)" :minLength="0" :completeOnFocus="true"
                            :dropdown="true" />
                    </template>
                    <template v-else>
                        <Select :modelValue="asString((data as Record<string, FormValue>)[field])"
                            :options="col.options ? [...col.options] : []" class="w-full"
                            @update:modelValue="setRowSelectValue(data, field, $event)" />
                    </template>
                </template>
            </Column>

            <!-- 行编辑按钮 -->
            <Column v-if="editableEnabled" :rowEditor="true" style="width: 6rem" />

            <!-- 删除按钮 -->
            <Column v-if="deletableEnabled" style="width:6rem">
                <template #body="{ data }">
                    <PrimeButton icon="pi pi-trash" size="small" severity="danger" @click="doDelete(data)" />
                </template>
            </Column>
        </DataTable>

        <!-- 添加记录弹窗 -->
        <PrimeDialog v-model:visible="createVisible" modal :header="`添加${columns[0]?.label || '记录'}`"
            :style="{ width: '50rem' }">
            <div class="grid grid-cols-2 gap-4">
                <div v-for="field in createFormFields" :key="field.key" class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {{ field.label }}<span v-if="field.required !== false">*</span>
                    </label>
                    <template v-if="field.type === 'text'">
                        <AutoComplete v-if="Array.isArray(field.suggestions)" class="w-full" inputClass="w-full"
                            :modelValue="asString(createForm[field.key])" :forceSelection="false" :dropdown="true"
                            :minLength="0" :completeOnFocus="true"
                            :suggestions="localSuggestions[`__local_create_${String(field.key)}`] ?? filterLocalSuggestions(field.suggestions, '')"
                            @complete="(e) => completeLocalSuggestions(`__local_create_${String(field.key)}`, field.suggestions!, e.query)"
                            @update:modelValue="(v) => setCreateTextValue(field.key, (v as any) ?? '')" />
                        <InputText v-else :modelValue="asString(createForm[field.key])"
                            @update:modelValue="setCreateTextValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'number'">
                        <InputNumber :modelValue="asNumber(createForm[field.key])" mode="decimal" :maxFractionDigits="2"
                            class="w-full" @update:modelValue="setCreateNumberValue(field.key, $event)" />
                    </template>
                    <template v-else-if="field.type === 'date'">
                        <DatePicker :modelValue="toDateModel(createForm[field.key])" dateFormat="yy-mm-dd" showIcon
                            inputClass="w-full"
                            @update:modelValue="(v) => setCreateDateValue(field.key, Array.isArray(v) ? (v[0] ?? null) : (v ?? null))" />
                    </template>
                    <template v-else-if="field.type === 'foreign'">
                        <AutoComplete v-model="createForm[field.key]" class="w-full" inputClass="w-full" :delay="300"
                            :forceSelection="true" :suggestions="foreignSuggestions[field.key] ?? []"
                            :optionLabel="field.foreign?.labelKey" @complete="completeForeign(field, $event.query)"
                            :minLength="0" :completeOnFocus="true" :dropdown="true" />
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
                <PrimeButton label="确认" :loading="submitting" @click="doCreate" />
            </template>
        </PrimeDialog>
        <!-- 删除确认框（分组），固定宽度 -->
        <ConfirmDialog group="dbtable-delete" :style="{ width: '32rem' }" />
    </div>
</template>