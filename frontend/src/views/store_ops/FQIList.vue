<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>FQI Reports</ion-title>
				<ion-buttons slot="end">
					<ion-button @click="createNewFQI">
						<ion-icon :icon="addOutline" />
					</ion-button>
				</ion-buttons>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Filter Tabs -->
			<ion-segment v-model="statusFilter" class="px-4 py-2">
				<ion-segment-button value="all">
					<ion-label>All</ion-label>
				</ion-segment-button>
				<ion-segment-button value="Open">
					<ion-label>Open</ion-label>
				</ion-segment-button>
				<ion-segment-button value="Resolved">
					<ion-label>Resolved</ion-label>
				</ion-segment-button>
			</ion-segment>

			<div v-if="reports.loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<ion-list v-else>
				<ion-item v-for="report in filteredReports" :key="report.name">
					<ion-icon :icon="warningOutline" slot="start"
						:class="report.status === 'Open' ? 'text-red-500' : 'text-gray-400'" />
					<ion-label>
						<h2>{{ report.name }}</h2>
						<p>{{ report.issue_type }} - {{ report.item_code }}</p>
						<p class="text-sm text-gray-500">{{ formatDate(report.reported_at) }}</p>
					</ion-label>
					<ion-badge slot="end" :color="report.status === 'Open' ? 'danger' : 'success'">
						{{ report.status }}
					</ion-badge>
				</ion-item>

				<EmptyState
					v-if="filteredReports.length === 0"
					message="No FQI reports found"
					buttonLabel="Report Issue"
					@action="createNewFQI"
				/>
			</ion-list>

			<!-- FAB for new FQI -->
			<ion-fab vertical="bottom" horizontal="end" slot="fixed">
				<ion-fab-button @click="createNewFQI" color="danger">
					<ion-icon :icon="addOutline" />
				</ion-fab-button>
			</ion-fab>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonIcon, IonList, IonLabel, IonItem,
	IonSpinner, IonBadge, IonFab, IonFabButton, IonSegment, IonSegmentButton
} from "@ionic/vue"
import { addOutline, warningOutline } from "ionicons/icons"
import { createResource } from "frappe-ui"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"

const router = useRouter()
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const statusFilter = ref("all")

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

// Fetch FQI reports
const reports = createResource({
	url: "hrms.api.store.get_fqi_reports",
	params: { store: store.value, limit: 50 },
	auto: false
})

const filteredReports = computed(() => {
	if (!reports.data?.reports) return []
	if (statusFilter.value === "all") return reports.data.reports
	return reports.data.reports.filter(r => r.status === statusFilter.value)
})

function formatDate(dateStr) {
	if (!dateStr) return ""
	return dayjs(dateStr).format("MMM D, YYYY h:mm A")
}

function createNewFQI() {
	router.push("/store/fqi/new")
}

onMounted(() => {
	if (store.value) {
		reports.fetch({ store: store.value, limit: 50 })
	}
})
</script>
