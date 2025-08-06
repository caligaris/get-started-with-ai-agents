import { Button, Spinner } from "@fluentui/react-components";
import { bundleIcon, DeleteFilled, DeleteRegular, GlobeSearchRegular } from "@fluentui/react-icons";
import { CopilotMessageV2 as CopilotMessage } from "@fluentui-copilot/react-copilot-chat";
import {
  ReferenceListV2 as ReferenceList,
  ReferenceOverflowButton,
  ReferenceV2 as Reference
} from "@fluentui-copilot/react-reference";
import { Suspense } from "react";

import { Markdown } from "../core/Markdown";
import { UsageInfo } from "./UsageInfo";
import { IAssistantMessageProps } from "./chatbot/types";

import styles from "./AgentPreviewChatBot.module.css";
import { AgentIcon } from "./AgentIcon";

const DeleteIcon = bundleIcon(DeleteFilled, DeleteRegular);

export function AssistantMessage({
  message,
  agentLogo,
  loadingState,
  agentName,
  showUsageInfo,
  onDelete,
}: IAssistantMessageProps): React.JSX.Element {
  //const hasAnnotations = message.annotations && message.annotations.length > 0;
  const hasAnnotations = false; // Temporarily disable annotations
  const references = hasAnnotations
    ? message.annotations?.map((annotation, index) => (
        <Reference 
          key={index} className="reference-item"
          citation={index + 1}
          graphic={<GlobeSearchRegular />}
          onClick={() => {
            // Open the file in a new tab or perform any action
            window.open(annotation.url_citation.url, "_blank");
          }}
        >
          {annotation.file_name}
        </Reference>
        // <div key={index} className="reference-item">
        //   {annotation.text || annotation.file_name}
        // </div>
      ))
    : [];

  return (
    <CopilotMessage
      id={"msg-" + message.id}
      key={message.id}
      actions={
        <span>
          {onDelete && message.usageInfo && (
            <Button
              appearance="subtle"
              icon={<DeleteIcon />}
              onClick={() => {
                void onDelete(message.id);
              }}
            />
          )}
        </span>
      }
      avatar={<AgentIcon alt="" iconName={agentLogo} />}
      className={styles.copilotChatMessage}
      disclaimer={<span>AI-generated content may be incorrect</span>}
      footnote={
        <>
          {hasAnnotations && (
            <ReferenceList
              maxVisibleReferences={3}
              minVisibleReferences={2}
              showLessButton={
                <ReferenceOverflowButton>Show Less</ReferenceOverflowButton>
              }
              showMoreButton={
                <ReferenceOverflowButton
                  text={(overflowCount) => `+${overflowCount.toString()}`}
                />
              }
            >
              {references}
            </ReferenceList>
          )}
          {showUsageInfo && message.usageInfo && (
            <UsageInfo info={message.usageInfo} duration={message.duration} />
          )}
        </>
      }
      loadingState={loadingState}
      name={agentName ?? "Bot"}
    >
      <Suspense fallback={<Spinner size="small" />}>
        <Markdown content={message.content} />
      </Suspense>
    </CopilotMessage>
  );
}
