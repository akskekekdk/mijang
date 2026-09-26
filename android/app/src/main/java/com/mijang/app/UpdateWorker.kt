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

/** 순위(하루 1번)와 시세(매번)를 갱신하고 알림을 띄운다. */
class UpdateWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val old = Store.load(applicationContext)
            val now = System.currentTimeMillis()
            val force = inputData.getBoolean(KEY_FORCE_RANK, false)
            val needRank = force || old == null || now - old.rankedAt > RANK_TTL_MS

            val ranked = if (needRank) rank() else old!!.stocks
            val rankedAt = if (needRank) now else old!!.rankedAt
            if (ranked.isEmpty()) return@withContext Result.retry()

            val quoted = parallel(ranked) { s ->
                runCatching { Yahoo.quote(s.ticker) }
                    .map { (price, prev) -> s.copy(price = price, prevClose = prev) }
                    .getOrDefault(s)
            }
            val snapshot = Snapshot(quoted, rankedAt, System.currentTimeMillis())
            Store.save(applicationContext, snapshot)
            Notifier.show(applicationContext, snapshot)
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }

    private suspend fun rank(): List<Stock> {
        val universe = Store.universe(applicationContext)
        val series = parallel(universe.keys.toList()) { t -> t to runCatching { Yahoo.weekly5y(t) }.getOrNull() }
            .mapNotNull { (t, s) -> s?.let { t to it } }
            .toMap()
        return Ranker.rank(series, universe, System.currentTimeMillis() / 1000)
    }

    private suspend fun <T, R> parallel(items: List<T>, block: (T) -> R): List<R> = coroutineScope {
        val limit = Semaphore(8)
        items.map { async { limit.withPermit { block(it) } } }.awaitAll()
    }

    companion object {
        private const val KEY_FORCE_RANK = "force_rank"
        private const val RANK_TTL_MS = 20L * 60 * 60 * 1000
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

        fun runNow(context: Context, forceRank: Boolean) {
            val request = OneTimeWorkRequestBuilder<UpdateWorker>()
                .setConstraints(network)
                .setInputData(workDataOf(KEY_FORCE_RANK to forceRank))
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.REPLACE, request)
        }
    }
}
