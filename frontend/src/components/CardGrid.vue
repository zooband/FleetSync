<script setup lang="ts">
withDefaults(
    defineProps<{
        columns?: 1 | 2 | 3 | 4
    }>(),
    {
        columns: 3,
    }
)
</script>

<template>
    <div class="grid gap-4" :class="{
        'grid-cols-1': true,
        'md:grid-cols-2': columns === 2 || columns === 4,
        'md:grid-cols-3': columns === 3,
        'xl:grid-cols-3': columns === 3,
        'xl:grid-cols-4': columns === 4,
    }">
        <slot />
    </div>
</template>
