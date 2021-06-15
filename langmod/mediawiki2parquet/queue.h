#pragma once

#include <condition_variable>
#include <mutex>
#include <optional>
#include <queue>
#include <vector>

namespace mediawiki {

template <typename T>
class Queue {
public:
    Queue(void) = default;

    /**
     * Constructor Queue initializes queue from vector of values. It internally
     * converts vector to deque in order to initialize underlying queue
     * object.
     */
    Queue(std::vector<T> const &values, bool closed = false)
        : queue_({values.begin(), values.end()})
        , closed_{closed}
    {}

    void Close(void) {
        closed_ = true;
    }

    bool Empty(void) const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }

    void Enqueue(T const &value) {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(value);
        condvar_.notify_one();
    }

    std::optional<T> Dequeue(void) {
        std::unique_lock<std::mutex> lock(mutex_);
        condvar_.wait(lock, [this] () {
            return closed_ || !queue_.empty();
        });

        if (!queue_.empty()) {
            T value =  queue_.front();
            queue_.pop();
            return value;
        } else {
            return std::nullopt;
        }
    }

private:
    std::condition_variable condvar_;
    mutable std::mutex mutex_;
    std::queue<T> queue_;
    bool closed_ = false;
};

} // namespace mediawiki
