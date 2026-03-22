<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>Store Receiving</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Expected Deliveries Section -->
			<ion-list>
				<ion-list-header>
					<ion-label>Expected Deliveries Today</ion-label>
				</ion-list-header>

				<div v-if="deliveries.loading" class="flex justify-center p-8">
					<ion-spinner />
				</div>

				<ion-item v-for="delivery in deliveries.data?.deliveries || []" :key="delivery.name"
					button @click="startReceiving(delivery)">
					<ion-icon :icon="cubeOutline" slot="start" class="text-blue-500" />
					<ion-label>
						<h2>Trip: {{ delivery.name }}</h2>
						<p>Route: {{ delivery.route_name }}</p>
						<p>Driver: {{ delivery.driver }} | Vehicle: {{ delivery.vehicle }}</p>
					</ion-label>
					<div slot="end" class="text-right">
						<ion-badge :color="getDeliveryStatusColor(delivery.status)">
							{{ delivery.status }}
						</ion-badge>
						<div class="text-sm mt-1">{{ delivery.items_count }} items</div>
					</div>
				</ion-item>

				<EmptyState
					v-if="!deliveries.loading && (!deliveries.data?.deliveries || deliveries.data.deliveries.length === 0)"
					message="No expected deliveries today"
				/>
			</ion-list>

			<!-- Recent Receiving Records -->
			<ion-list class="mt-4">
				<ion-list-header>
					<ion-label>Recent Receiving</ion-label>
				</ion-list-header>

				<ion-item v-for="record in recentReceiving" :key="record.name">
					<ion-label>
						<h2>{{ record.name }}</h2>
						<p>{{ record.receiving_date }}</p>
					</ion-label>
					<ion-badge slot="end" :color="record.status === 'Completed' ? 'success' : 'warning'">
						{{ record.status }}
					</ion-badge>
				</ion-item>
			</ion-list>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonList, IonListHeader, IonLabel, IonItem,
	IonSpinner, IonBadge, IonIcon
} from "@ionic/vue"
import { cubeOutline } from "ionicons/icons"
import { createResource } from "frappe-ui"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"

const router = useRouter()
const employee = inject("$employee")

const recentReceiving = ref([])

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

// Fetch expected deliveries
const deliveries = createResource({
	url: "hrms.api.store.get_expected_deliveries",
	params: { store: store.value },
	auto: false
})

function startReceiving(delivery) {
	router.push(`/store/receiving/${delivery.name}`)
}

function getDeliveryStatusColor(status) {
	const colors = {
		"Preparing": "medium",
		"In Transit": "primary",
		"Completed": "success",
		"Partial": "warning"
	}
	return colors[status] || "medium"
}

onMounted(() => {
	if (store.value) {
		deliveries.fetch({ store: store.value })
	}
})
</script>
