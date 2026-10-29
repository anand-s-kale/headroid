// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

/** One JSON-RPC method. The returned value is written as {@code result} (null becomes {@code {}}). */
public interface RpcMethod {
    Object call(Params params) throws Exception;
}
