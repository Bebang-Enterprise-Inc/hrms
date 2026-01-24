<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>Dispatch Tracker</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Date Selector -->
			<div class="p-4 bg-gray-50 border-b">
				<ion-datetime-button datetime="tripDate" />
				<ion-modal :keep-contents-mounted="true">
					<ion-datetime
						id="tripDate"
						presentation="date"
						v-model="selectedDate"
						@ionChange="loadTrips"
					/>
				</ion-modal>
			</div>

			<!-- Stats Overview -->
			<div class="p-4 grid grid-cols-3 gap-3">
				<div class="bg-blue-50 p-3 rounded-lg text-center">
					<div class="text-2xl font-bold text-blue-600">{{ stats.preparing }}</div>
					<div class="text-xs text-gray-500">Preparing</div>
				</div>
				<div class="bg-green-50 p-3 rounded-lg text-center">
					<div class="text-2xl font-bold text-green-600">{{ stats.inTransit }}</div>
					<div class="text-xs text-gray-500">In Transit</div>
				</div>
				<div class="bg-gray-50 p-3 rounded-lg text-center">
					<div class="text-2xl font-bold text-gray-600">{{ stats.completed }}</div>
					<div class="text-xs text-gray-500">Completed</div>
				</div>
			</div>

			<div v-if="trips.loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<!-- Trip List -->
			<ion-list v-else>
				<ion-list-header>
					<ion-label>Today's Trips</ion-label>
				</ion-list-header>

				<ion-item v-for="trip in trips.data?.trips || []" :key="trip.name"
					button @click="viewTrip(trip.name)">
					<ion-icon :icon="carOutline" slot="start" :class="getTripIconColor(trip.status)" />
					<ion-label>
						<h2 class="font-medium">{{ trip.route_name || trip.name }}</h2>
						<p>Driver: {{ trip.driver || 'Not assigned' }}</p>
						<p>{{ trip.vehicle }} {{ trip.vehicle_plate }}</p>
					</ion-label>
					<div slot="end" class="text-right">
						<ion-badge :color="getTripStatusColor(trip.status)">
							{{ trip.status }}
						</ion-badge>
						<div class="text-sm mt-1">
							{{ trip.delivered_stops }}/{{ trip.total_stops }} stops
						</div>
					</div>
				</ion-item>

				<EmptyState
					v-if="(!trips.data?.trips || trips.data.trips.length === 0)"
					message="No trips scheduled for this date"
				/>
			</ion-list>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonList, IonListHeader, IonLabel, IonItem,
	IonSpinner, IonBadge, IonIcon, IonDatetime, IonDatetimeButton, IonModal
} from "@ionic/vue"
import { carOutline } from "ionicons/icons"
import { createResource } from "frappe-ui"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"

const router = useRouter()
const dayjs = inject("$dayjs")

const selectedDate = ref(dayjs().format("YYYY-MM-DD"))

const stats = ref({
	preparing: 0,
	inTransit: 0,
	completed: 0
})

// Fetch trips
const trips = createResource({
	url: "hrms.api.dispatch.get_trips",
	params: { date: selectedDate.value },
	auto: true,
	onSuccess(data) {
		if (data?.trips) {
			stats.value.preparing = data.trips.filter(t => t.status === "Preparing").length
			stats.value.inTransit = data.trips.filter(t => t.status === "In Transit").length
			stats.value.completed = data.trips.filter(t => t.status === "Completed").length
		}
	}
})

function loadTrips() {
	trips.fetch({ date: selectedDate.value })
}

function viewTrip(tripId) {
	router.push(`/dispatch/trip/${tripId}`)
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

function getTripIconColor(status) {
	const colors = {
		"Preparing": "text-gray-400",
		"In Transit": "text-blue-500",
		"Completed": "text-green-500",
		"Partial": "text-yellow-500"
	}
	return colors[status] || "text-gray-400"
}

onMounted(() => {
	loadTrips()
})
</script>
