#!/usr/bin/env ruby
# frozen_string_literal: true

require "set"
require "base64"
require "yaml"

root = File.expand_path("..", __dir__)
dashboard_path = File.join(root, "dashboards", "hi-lab-operations.yaml")
dashboard = YAML.safe_load(
  File.read(dashboard_path, encoding: "UTF-8"),
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false,
  filename: dashboard_path
)

def fail_contract(message)
  warn "dashboard contract: #{message}"
  exit 1
end

fail_contract("top level must be a mapping") unless dashboard.is_a?(Hash)
fail_contract("title differs") unless dashboard["title"] == "HI Lab Controller"
views = dashboard["views"]
fail_contract("operations and evidence views are required") unless views.is_a?(Array) && views.length == 2
view_paths = views.map { |view| view.is_a?(Hash) ? view["path"] : nil }
fail_contract("view paths differ: #{view_paths.inspect}") unless view_paths == [
  "hi-lab-controller", "hi-lab-controller-evidence"
]
views.each do |view|
  fail_contract("every view must use sections") unless view["type"] == "sections"
  fail_contract("every view must use a two-column responsive maximum") unless view["max_columns"] == 2
  fail_contract("every view must preserve ordered section placement") unless view["dense_section_placement"] == false
  header = view["header"]
  fail_contract("every view must have a responsive header") unless (
    header.is_a?(Hash) && header["layout"] == "responsive"
  )
end
wide_sections = views.map do |view|
  Array(view["sections"]).count { |section| section.is_a?(Hash) && section["column_span"] == 2 }
end
fail_contract("every view must have one deliberate full-width section") unless wide_sections == [1, 1]

operations_sections = Array(views.first["sections"])
operations_headings = operations_sections.map do |section|
  Array(section["cards"]).find { |card| card.is_a?(Hash) && card["type"] == "heading" }&.fetch("heading", nil)
end
expected_operations_headings = [
  "System pulse",
  "Contact and restart",
  "Deployment lifecycle",
  "Baseline acceptance",
  "Validation, outcome and queue"
]
fail_contract("Operations section order differs: #{operations_headings.inspect}") unless (
  operations_headings == expected_operations_headings
)
fail_contract("the first two Operations rows must remain paired, not full-width") unless (
  operations_sections.first(4).none? { |section| section["column_span"] }
)

contact_cards = Array(operations_sections[1]["cards"])
last_contact_card = contact_cards.find do |card|
  card.is_a?(Hash) && card["type"] == "tile" && card["name"] == "Last valid controller contact"
end
fail_contract("Last valid controller contact must be a compact full-section tile") unless (
  last_contact_card && last_contact_card["grid_options"] == {"columns" => 12, "rows" => 2}
)
restart_summary_cards = contact_cards.each_with_object([]) do |card, found|
  next unless card.is_a?(Hash) && card["type"] == "conditional" && card["card"].is_a?(Hash)
  next unless ["Restart not required", "Restart required", "Restart truth unavailable"].include?(card["card"]["title"])

  found << card
end
restart_summary_layouts = restart_summary_cards.to_h do |card|
  [card["card"]["title"], card["grid_options"]]
end
fail_contract("Contact and restart must cover all three restart presentations") unless (
  restart_summary_layouts == {
    "Restart not required" => {"columns" => 12, "rows" => 2},
    "Restart required" => {"columns" => 12, "rows" => 4},
    "Restart truth unavailable" => {"columns" => 12, "rows" => 2}
  }
)

deployment_cards = Array(operations_sections[2]["cards"])
lifecycle_note = deployment_cards.find do |card|
  card.is_a?(Hash) && card["type"] == "markdown" && card["content"].include?("Three separate facts")
end
fail_contract("Deployment lifecycle note must balance its paired section") unless (
  lifecycle_note && lifecycle_note["grid_options"] == {"columns" => 12, "rows" => 3}
)

baseline_cards = Array(operations_sections[3]["cards"])
baseline_tiles = baseline_cards.select do |card|
  card.is_a?(Hash) && card["type"] == "conditional" && card.dig("card", "entity") == "sensor.hi_lab_controller_accepted_baseline"
end
fail_contract("all baseline states must use the same full-section tile geometry") unless (
  baseline_tiles.length == 3 && baseline_tiles.all? do |card|
    card["grid_options"] == {"columns" => 12, "rows" => 3}
  end
)
acceptance_note = baseline_cards.find do |card|
  card.is_a?(Hash) && card["type"] == "markdown" && card["title"] == "Acceptance boundary"
end
fail_contract("Baseline acceptance must retain its compact truth boundary") unless (
  acceptance_note && acceptance_note["grid_options"] == {"columns" => 12, "rows" => 2}
)

expected_entities = Set[
  "sensor.hi_lab_controller_feed",
  "sensor.hi_lab_controller_last_contact",
  "sensor.hi_lab_controller_readiness",
  "sensor.hi_lab_controller_active_deployment",
  "sensor.hi_lab_controller_pending_deployment",
  "sensor.hi_lab_controller_mutation_lock",
  "sensor.hi_lab_controller_accepted_baseline",
  "sensor.hi_lab_controller_last_validation",
  "sensor.hi_lab_controller_last_outcome",
  "sensor.hi_lab_controller_prepare_queue",
  "binary_sensor.hi_lab_controller_restart_required"
]
allowed_card_types = Set[
  "sections", "grid", "heading", "markdown", "conditional", "tile", "entities", "attribute",
  "button"
]
documented_attributes = {
  "sensor.hi_lab_controller_feed" => Set[
    "supported_schema_majors", "observed_schema_major", "error_code",
    "controller_boot_id", "state_revision", "generated_at", "expires_at"
  ],
  "sensor.hi_lab_controller_last_contact" => Set["historical_only"],
  "sensor.hi_lab_controller_readiness" => Set["blocker_codes", "overflow_count", "state_revision"],
  "sensor.hi_lab_controller_active_deployment" => Set[
    "profile", "manifest_version", "verified_at", "accepted_baseline"
  ],
  "sensor.hi_lab_controller_pending_deployment" => Set[
    "state", "profile", "manifest_version", "previous_deployment_id", "created_at", "updated_at"
  ],
  "sensor.hi_lab_controller_mutation_lock" => Set["deployment_id", "owner_kind", "held_at"],
  "sensor.hi_lab_controller_accepted_baseline" => Set[
    "target_slot", "profile", "manifest_version", "accepted_at"
  ],
  "sensor.hi_lab_controller_last_validation" => Set[
    "deployment_id", "installed_identity", "stage_b_verdict", "stage_b_passed",
    "stage_b_expected", "stage_3_verdict", "stage_3_passed", "stage_3_expected"
  ],
  "sensor.hi_lab_controller_last_outcome" => Set[
    "deployment_id", "profile", "completed_at", "error_codes"
  ],
  "sensor.hi_lab_controller_prepare_queue" => Set["enabled", "depth", "max_depth", "entries"],
  "binary_sensor.hi_lab_controller_restart_required" => Set[
    "deployment_id", "reason_code", "approved"
  ]
}.freeze

entities = Set.new
card_types = Set.new
attribute_rows = []
template_attributes = []
forbidden_keys = Set["service", "service_data", "hold_action", "double_tap_action"]
semantic_tiles = {}
navigation_cards = []
action_hashes = []
queue_context_cards = []
validation_coverage_cards = []

positive_states = lambda do |conditions, found = []|
  Array(conditions).each do |condition|
    next unless condition.is_a?(Hash)

    if condition["condition"] == "state" && condition["entity"].is_a?(String) && condition.key?("state")
      found << [condition["entity"], condition["state"]]
    elsif %w[and or].include?(condition["condition"])
      positive_states.call(condition["conditions"], found)
    end
  end
  found
end

walk = lambda do |value|
  case value
  when Hash
    navigation_cards << value if value["type"] == "button" && value.key?("tap_action")
    queue_context_cards << value if value["type"] == "markdown" && value["title"] == "Queue context"
    validation_coverage_cards << value if (
      value["type"] == "entities" && value["title"] == "Validation coverage" && value.key?("grid_options")
    )
    action_hashes << value if value.key?("action")
    if value["type"] == "conditional" && value["card"].is_a?(Hash) && value["card"]["type"] == "tile"
      color = value["card"]["color"]
      positive_states.call(value["conditions"]).each do |entity, state|
        semantic_tiles[[entity, state]] = color
      end
    end
    value.each do |key, child|
      fail_contract("interactive or service key #{key.inspect} is forbidden") if forbidden_keys.include?(key)
      card_types << child if key == "type" && child.is_a?(String)
      entities << child if key == "entity" && child.is_a?(String)
      walk.call(child)
    end
    if value["type"] == "attribute"
      attribute_rows << [value["entity"], value["attribute"]]
    end
  when Array
    value.each { |child| walk.call(child) }
  when String
    value.scan(/(?:binary_sensor|sensor)\.hi_lab_controller_[a-z0-9_]+/) { |entity| entities << entity }
    value.scan(/state_attr\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\)/) do |entity, attribute|
      template_attributes << [entity, attribute]
    end
  end
end
walk.call(dashboard)

fail_contract("entity set differs: #{entities.to_a.sort.inspect}") unless entities == expected_entities
unknown_types = card_types - allowed_card_types
fail_contract("non-native card types found: #{unknown_types.to_a.sort.inspect}") unless unknown_types.empty?

expected_navigation_card = {
  "type" => "button",
  "name" => "Open Actions tool",
  "icon" => "mdi:hammer-wrench",
  "show_name" => true,
  "show_icon" => true,
  "tap_action" => {
    "action" => "navigate",
    "navigation_path" => "/config/developer-tools/action"
  },
  "grid_options" => {"columns" => 12, "rows" => 3}
}.freeze
fail_contract("exactly one bounded Actions-tool navigation button is required") unless (
  navigation_cards == [expected_navigation_card]
)
fail_contract("the only action must be the bounded Actions-tool navigation") unless (
  action_hashes == [{"action" => "navigate", "navigation_path" => "/config/developer-tools/action"}]
)
expected_queue_context = queue_context_cards.one? &&
                         queue_context_cards.first["grid_options"] == {"columns" => 12, "rows" => 3}
fail_contract("one always-present half-width Queue context card is required") unless expected_queue_context
%w[DISABLED EMPTY WAITING FULL].each do |state|
  fail_contract("Queue context must distinguish #{state}") unless queue_context_cards.first["content"].include?(state)
end
expected_validation_coverage = validation_coverage_cards.one? &&
                               validation_coverage_cards.first["grid_options"] == {
                                 "columns" => "full", "rows" => 4
                               }
fail_contract("Operations Validation coverage must be full-width and four rows") unless (
  expected_validation_coverage
)

(attribute_rows + template_attributes).each do |entity, attribute|
  allowed = documented_attributes.fetch(entity) do
    fail_contract("attribute reference uses unknown entity #{entity.inspect}")
  end
  fail_contract("undocumented attribute #{entity}.#{attribute}") unless allowed.include?(attribute)
end

raw = File.read(dashboard_path, encoding: "UTF-8")
brand_path = File.join(root, "brand", "icon.png")
preview_path = File.join(root, "docs", "images", "hi-lab-operations-dashboard.svg")
preview = File.read(preview_path, encoding: "UTF-8")
embedded_brand = preview.match(%r{data:image/png;base64,([A-Za-z0-9+/=]+)})
fail_contract("official brand image is not embedded in the public preview") unless embedded_brand
fail_contract("embedded public-preview brand image differs") unless (
  Base64.strict_decode64(embedded_brand[1]) == File.binread(brand_path)
)
%w[stale missing invalid_signature schema_mismatch clock_invalid BLOCKED UNAVAILABLE DISABLED].each do |state|
  fail_contract("required degraded-state truth #{state.inspect} is absent") unless raw.include?(state)
end
%w[green amber red].each do |color|
  fail_contract("required semantic color #{color.inspect} is absent") unless raw.include?("color: #{color}")
end
expected_semantic_tiles = {
  ["sensor.hi_lab_controller_feed", "fresh"] => "green",
  ["sensor.hi_lab_controller_readiness", "READY"] => "green",
  ["sensor.hi_lab_controller_readiness", "BLOCKED"] => "red",
  ["sensor.hi_lab_controller_readiness", "unknown"] => "red",
  ["sensor.hi_lab_controller_readiness", "unavailable"] => "red",
  ["sensor.hi_lab_controller_mutation_lock", "CLEAR"] => "green",
  ["sensor.hi_lab_controller_mutation_lock", "HELD"] => "amber",
  ["binary_sensor.hi_lab_controller_restart_required", "off"] => "green",
  ["binary_sensor.hi_lab_controller_restart_required", "on"] => "amber",
  ["binary_sensor.hi_lab_controller_restart_required", "unavailable"] => "red",
  ["sensor.hi_lab_controller_active_deployment", "none"] => "blue-grey",
  ["sensor.hi_lab_controller_active_deployment", "unknown"] => "red",
  ["sensor.hi_lab_controller_active_deployment", "unavailable"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "ACTIVE"] => "green",
  ["sensor.hi_lab_controller_last_outcome", "NO_CHANGE_EQUIVALENT_PACKAGE"] => "green",
  ["sensor.hi_lab_controller_last_outcome", "RESTORED_PRE_ACTIVATION"] => "amber",
  ["sensor.hi_lab_controller_last_outcome", "ROLLED_BACK"] => "amber",
  ["sensor.hi_lab_controller_last_outcome", "DISCARDED"] => "blue-grey",
  ["sensor.hi_lab_controller_last_outcome", "BLOCKED"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "FAILED_ACTIVATION"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "FAILED_PRE_DEPLOY"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "RECOVERY_REQUIRED"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "unknown"] => "red",
  ["sensor.hi_lab_controller_last_outcome", "unavailable"] => "red",
  ["sensor.hi_lab_controller_prepare_queue", "DISABLED"] => "blue-grey",
  ["sensor.hi_lab_controller_prepare_queue", "EMPTY"] => "green",
  ["sensor.hi_lab_controller_prepare_queue", "WAITING"] => "amber",
  ["sensor.hi_lab_controller_prepare_queue", "FULL"] => "amber",
  ["sensor.hi_lab_controller_prepare_queue", "BLOCKED"] => "red",
  ["sensor.hi_lab_controller_prepare_queue", "DEGRADED"] => "red",
  ["sensor.hi_lab_controller_prepare_queue", "UNAVAILABLE"] => "red"
}.freeze
expected_semantic_tiles.each do |key, expected_color|
  actual_color = semantic_tiles[key]
  fail_contract("semantic tile #{key.join('=')} must be #{expected_color}, got #{actual_color.inspect}") unless (
    actual_color == expected_color
  )
end
fail_contract("custom cards are forbidden") if raw.include?("custom:")
fail_contract("historical contact must not use Home Assistant last_updated") if raw.include?("last_updated")
["Integration health", "Runtime truth"].each do |public_name|
  fail_contract("public validation name #{public_name.inspect} is absent") unless raw.include?(public_name)
end
["Operations", "Evidence", "Open Actions tool"].each do |surface_name|
  fail_contract("preview surface name #{surface_name.inspect} is absent") unless preview.include?(surface_name)
end

puts(
  "dashboard contract: PASS " \
  "(#{entities.length} entities, #{attribute_rows.length} attribute rows, " \
  "#{template_attributes.length} template attribute references)"
)
