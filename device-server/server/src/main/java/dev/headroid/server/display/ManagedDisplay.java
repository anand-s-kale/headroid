// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

/** A display created and owned by this server. */
public interface ManagedDisplay {
    int id();

    void release();
}
