<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/dispatch" />
				</ion-buttons>
				<ion-title>Trip Details</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="tripDetails.loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<template v-else-if="trip">
				<!-- Trip Header -->
				<div class="p-4 bg-gray-50 border-b">
					<div class="flex justify-between items-center">
						<div>
							<h2 class="text-lg font-bold">{{ trip.route_name || trip.name }}</h2>
							<p class="text-gray-500">{{ trip.trip_date }}</p>
						</div>
						<ion-badge :color="getTripStatusColor(trip.status)" class="text-lg px-3 py-1">
							{{ trip.status }}
						</ion-badge>
					</div>
					<div class="mt-3 grid grid-cols-2 gap-2 text-sm">
						<div><span class="text-gray-500">Driver:</span> {{ trip.driver || '-' }}</div>
						<div><span class="text-gray-500">Vehicle:</span> {{ trip.vehicle }} {{ trip.vehicle_plate }}</div>
						<div v-if="trip.departure_time"><span class="text-gray-500">Departed:</span> {{ formatTime(trip.departure_time) }}</div>
						<div v-if="trip.departure_temp"><span class="text-gray-500">Temp:</span> {{ trip.departure_temp }}°C</div>
					</div>
				</div>

				<!-- Departure Button (if Preparing) -->
				<div v-if="trip.status === 'Preparing'" class="p-4">
					<ion-button expand="block" @click="startDeparture">
						Start Departure Checklist
					</ion-button>
				</div>

				<!-- Stops List -->
				<ion-list>
					<ion-list-header>
						<ion-label>Delivery Stops ({{ trip.stops?.length || 0 }})</ion-label>
					</ion-list-header>

					<ion-item v-for="stop in trip.stops" :key="stop.idx"
						:button="trip.status === 'In Transit' && stop.status === 'Pending'"
						@click="goToStop(stop)">
						<div slot="start" class="w-8 h-8 rounded-full flex items-center justify-center"
							:class="getStopBgColor(stop.status)">
							<ion-icon :icon="getStopIcon(stop.status)" :class="getStopIconColor(stop.status)" />
						</div>
						<ion-label>
							<h2>{{ stop.stop_order }}. {{ stop.store }}</h2>
							<p>{{ stop.items_count }} items</p>
							<p v-if="stop.arrival_time" class="text-sm text-gray-500">
								{{ formatTime(stop.arrival_time) }}
								<span v-if="stop.signed_by"> - {{ stop.signed_by }}</span>
							</p>
							<p v-if="stop.exception_reason" class="text-sm text-red-500">
								{{ stop.exception_reason }}
							</p>
						</ion-label>
						<ion-badge slot="end" :color="getStopStatusColor(stop.status)">
							{{ stop.status }}
						</ion-badge>
					</ion-item>
				</ion-list>
			</template>

			<EmptyState v-else message="Trip not found" />
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonList, IonListHeader, IonLabel, IonItem,
	IonSpinner, IonBadge, IonButton, IonIcon
} from "@ionic/vue"
import { checkmarkCircle, alertCircle, ellipse, closeCircle } from "ionicons/icons"
import { createResource } from "frappe-ui"
import { computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"

const router = useRouter()
const dayjs = inject("$dayjs")

const props = defineProps({
	id: { type: String, required: true }
})

// Fetch trip details
const tripDetails = createResource({
	url: "hrms.api.dispatch.get_trip_detail",
	params: { trip_name: props.id },
	auto: true
})

const trip = computed(() => tripDetails.data?.trip)

function formatTime(dateStr) {
	if (!dateStr) return ""
	return dayjs(dateStr).format("h:mm A")
}

function startDeparture() {
	router.push(`/dispatch/trip/${props.id}/departure`)
}

function goToStop(stop) {
	if (trip.value?.status === "In Transit" && stop.status === "Pending") {
		router.push(`/dispatch/trip/${props.id}/stop/${stop.idx}`)
	}
}

function getTripStatusColor(status) {
	const colors = {
		"Preparing": "medium",
		"In Transit": "primary",
		"Completed": "success",
		"Partial": "warning"
	}
	return colors[status] || "medium"
}

function getStopStatusColor(status) {
	const colors = {
		"Pending": "medium",
		"Delivered": "success",
		"Store Closed": "warning",
		"Refused": "danger"
	}
	return colors[status] || "medium"
}

function getStopBgColor(status) {
	const colors = {
		"Pending": "bg-gray-100",
		"Delivered": "bg-green-100",
		"Store Closed": "bg-yellow-100",
		"Refused": "bg-red-100"
	}
	return colors[status] || "bg-gray-100"
}

function getStopIconColor(status) {
	const colors = {
		"Pending": "text-gray-400",
		"Delivered": "text-green-500",
		"Store Closed": "text-yellow-500",
		"Refused": "text-red-500"
	}
	return colors[status] || "text-gray-400"
}

function getStopIcon(status) {
	const icons = {
		"Pending": ellipse,
		"Delivered": checkmarkCircle,
		"Store Closed": alertCircle,
		"Refused": closeCircle
	}
	return icons[status] || ellipse
}

onMounted(() => {
	tripDetails.fetch({ trip_name: props.id })
})
</script>
