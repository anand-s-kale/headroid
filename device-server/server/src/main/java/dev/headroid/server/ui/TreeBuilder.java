// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Serializes window roots into wire-protocol nodes whose ids are index paths ("window.child.child"). */
public final class TreeBuilder {

    private static final String[] FLAG_NAMES = {
        "clickable", "longClickable", "enabled", "focused", "focusable", "scrollable", "checkable", "checked", "editable", "selected",
        "visible",
    };

    private TreeBuilder() {
        // not instantiable
    }

    public static List<Map<String, Object>> build(List<? extends NodeView> windowRoots, int maxDepth) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (int i = 0; i < windowRoots.size(); i++) {
            NodeView root = windowRoots.get(i);
            if (root != null) {
                result.add(node(root, String.valueOf(i), 0, maxDepth));
            }
        }
        return result;
    }

    private static Map<String, Object> node(NodeView view, String id, int depth, int maxDepth) {
        Map<String, Object> node = new LinkedHashMap<>();
        node.put("id", id);
        node.put("cls", view.cls());
        node.put("pkg", view.pkg());
        node.put("text", view.text());
        node.put("desc", view.desc());
        node.put("rid", view.rid());
        node.put("bounds", view.bounds());
        int flags = view.flags();
        for (int bit = 0; bit < FLAG_NAMES.length; bit++) {
            node.put(FLAG_NAMES[bit], (flags & (1 << bit)) != 0);
        }
        List<Map<String, Object>> children = new ArrayList<>();
        if (depth < maxDepth) {
            int count = view.childCount();
            for (int i = 0; i < count; i++) {
                NodeView child = view.child(i);
                if (child != null) {
                    children.add(node(child, id + "." + i, depth + 1, maxDepth));
                }
            }
        }
        node.put("children", children);
        return node;
    }
}
