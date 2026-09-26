package com.mijang.app

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/** 예측 결과(3시간마다)와 시세(매번)를 갱신하고 알림을 띄운다. */
class UpdateWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val old = Store.load(applicationContext)
            val now = System.currentTimeMillis()
            val force = inputData.getBoolean(KEY_FORCE_FETCH, false)
            val needFetch = force || old == null || now - old.fetchedAt > FETCH_TTL_MS

            val prediction = if (needFetch) Predictions.fetch() else old!!.prediction
            val fetchedAt = if (needFetch) now else old!!.fetchedAt
            if (prediction.stocks.isEmpty()) return@withContext Result.retry()

            val quoted = parallel(prediction.stocks) { s ->
                runCatching { Yahoo.quote(s.ticker) }
                    .map { (price, prev) -> s.copy(price = price, prevClose = prev) }
                    .getOrDefault(s)
            }
            val snapshot = Snapshot(prediction.copy(stocks = quoted), fetchedAt, System.currentTimeMillis())
            Store.save(applicationContext, snapshot)
            Notifier.show(applicationContext, snapshot)
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }

    private suspend fun <T, R> parallel(items: List<T>, block: (T) -> R): List<R> = coroutineScope {
        val limit = Semaphore(8)
        items.map { async { limit.withPermit { block(it) } } }.awaitAll()
    }

    companion object {
        private const val KEY_FORCE_FETCH = "force_fetch"
        private const val FETCH_TTL_MS = 3L * 60 * 60 * 1000
        const val PERIODIC = "mijang-periodic"
        const val NOW = "mijang-now"

        private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        /** 1시간마다 자동 갱신 (이미 등록돼 있으면 유지). */
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<UpdateWorker>(1, TimeUnit.HOURS)
                .setConstraints(network)
                .build()
            WorkManager.getInstance(context)
                .enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, request)
        }

        fun runNow(context: Context, forceFetch: Boolean) {
            val request = OneTimeWorkRequestBuilder<UpdateWorker>()
                .setConstraints(network)
                .setInputData(workDataOf(KEY_FORCE_FETCH to forceFetch))
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.REPLACE, request)
        }
    }
}
