// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

import org.junit.Assert;
import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

public class TreeBuilderTest {

    static final class FakeNode implements NodeView {
        final String cls;
        final String text;
        final List<NodeView> children = new ArrayList<>();
        boolean clickable;

        FakeNode(String cls, String text, NodeView... children) {
            this.cls = cls;
            this.text = text;
            this.children.addAll(Arrays.asList(children));
        }

        @Override public String cls() { return cls; }
        @Override public String pkg() { return "dev.headroid.sample"; }
        @Override public String text() { return text; }
        @Override public String desc() { return null; }
        @Override public String rid() { return text == null ? null : "dev.headroid.sample:id/" + text; }
        @Override public int[] bounds() { return new int[] {1, 2, 3, 4}; }
        @Override public int flags() { return clickable ? NodeView.CLICKABLE | NodeView.VISIBLE : NodeView.VISIBLE; }
        @Override public int childCount() { return children.size(); }
        @Override public NodeView child(int index) { return children.get(index); }
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> children(Map<String, Object> node) {
        return (List<Map<String, Object>>) node.get("children");
    }

    @Test
    public void idsAreIndexPaths() {
        FakeNode root0 = new FakeNode("FrameLayout", null, new FakeNode("Button", "a"),
                new FakeNode("LinearLayout", null, new FakeNode("Text", "b")));
        FakeNode root1 = new FakeNode("Dialog", "d");
        List<Map<String, Object>> tree = TreeBuilder.build(Arrays.asList(root0, root1), 80);
        Assert.assertEquals(2, tree.size());
        Assert.assertEquals("0", tree.get(0).get("id"));
        Assert.assertEquals("1", tree.get(1).get("id"));
        Map<String, Object> b = children(children(tree.get(0)).get(1)).get(0);
        Assert.assertEquals("0.1.0", b.get("id"));
        Assert.assertEquals("b", b.get("text"));
    }

    @Test
    public void boundsAndFlagsSerialized() {
        FakeNode button = new FakeNode("android.widget.Button", "login_submit");
        button.clickable = true;
        Map<String, Object> node = TreeBuilder.build(Collections.singletonList(button), 80).get(0);
        Assert.assertArrayEquals(new int[] {1, 2, 3, 4}, (int[]) node.get("bounds"));
        Assert.assertEquals(Boolean.TRUE, node.get("clickable"));
        Assert.assertEquals(Boolean.FALSE, node.get("editable"));
        Assert.assertEquals(Boolean.TRUE, node.get("visible"));
        Assert.assertEquals("dev.headroid.sample:id/login_submit", node.get("rid"));
        Assert.assertEquals("android.widget.Button", node.get("cls"));
        Assert.assertTrue(node.containsKey("desc"));
    }

    @Test
    public void depthLimited() {
        NodeView node = new FakeNode("V", "x");
        for (int i = 0; i < 10; i++) {
            node = new FakeNode("V", null, node);
        }
        Map<String, Object> level = TreeBuilder.build(Collections.singletonList(node), 3).get(0);
        int depth = 0;
        while (!children(level).isEmpty()) {
            level = children(level).get(0);
            depth++;
        }
        Assert.assertEquals(3, depth);
    }

    @Test
    public void nullChildSkipped() {
        FakeNode root = new FakeNode("Root", null, new FakeNode("A", "a"));
        root.children.add(0, null);
        Map<String, Object> node = TreeBuilder.build(Collections.singletonList(root), 80).get(0);
        Assert.assertEquals(1, children(node).size());
        Assert.assertEquals("0.1", children(node).get(0).get("id"));
    }

    @Test
    public void nullRootSkipped() {
        List<NodeView> roots = new ArrayList<>();
        roots.add(null);
        roots.add(new FakeNode("A", "a"));
        List<Map<String, Object>> tree = TreeBuilder.build(roots, 80);
        Assert.assertEquals(1, tree.size());
        Assert.assertEquals("1", tree.get(0).get("id"));
    }
}
